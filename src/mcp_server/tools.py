"""The MCP tools. Each tool only calls the core and turns its answer into JSON."""

from collections.abc import Callable
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from core import (
    FrequencyTable,
    VocabStore,
    WordFacts,
    analyse,
    find_episode,
    new_words,
    pick_lesson_words,
    read_lines,
    subtitle_file,
)
from core.frequency import DEFAULT_FREQUENCY
from core.subtitles import Line
from core.word_facts import DEFAULT_FACTS
from web.launch import PageError

_EPISODE = {
    "type": "string",
    "description": 'The Episode name under the media folder, for example "Dark/S01E03".',
}

_WORD = {
    "type": "object",
    "properties": {
        "base_form": {"type": "string"},
        "word_type": {"type": "string"},
    },
    "required": ["base_form", "word_type"],
    "additionalProperties": False,
}

_JSON_TYPES = {"string": str, "array": list, "object": dict}


class Page(Protocol):
    def open(self, episode: str) -> str:
        """Open the exercise page of an Episode; give its URL."""


class ToolError(Exception):
    """A tool call that cannot be done, for example an unknown Episode."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    properties: dict
    handler: Callable

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": self.properties,
            "required": list(self.properties),
            "additionalProperties": False,
        }

    def check(self, arguments: dict) -> None:
        missing = set(self.properties) - set(arguments)
        extra = set(arguments) - set(self.properties)
        if missing or extra:
            raise ToolError(
                f"{self.name} needs exactly {sorted(self.properties)}; "
                f"missing {sorted(missing)}, not known {sorted(extra)}"
            )
        for key, value in arguments.items():
            _check_value(key, value, self.properties[key])


def _check_value(name: str, value, schema: dict) -> None:
    """Check a value against the small part of JSON Schema the tools use."""
    if not isinstance(value, _JSON_TYPES[schema["type"]]):
        raise ToolError(f"{name} must be of type {schema['type']}")
    if schema["type"] == "array":
        for item in value:
            _check_value(f"each item of {name}", item, schema["items"])
    if schema["type"] == "object":
        fields = schema["properties"]
        if set(value) != set(fields):
            raise ToolError(f"{name} must have exactly {sorted(fields)}")
        for key, field_value in value.items():
            _check_value(f"{key} in {name}", field_value, fields[key])


class Toolbox:
    """The tools the agents can call. Each one is a thin call into the core."""

    def __init__(
        self,
        media_root: Path | str,
        db_path: Path | str,
        page: Page,
        facts_path: Path | str = DEFAULT_FACTS,
        frequency_path: Path | str = DEFAULT_FREQUENCY,
    ):
        self._media_root = Path(media_root)
        self._db_path = Path(db_path)
        self._facts_path = Path(facts_path)
        self._frequency_path = Path(frequency_path)
        self._page = page
        self.tools = {
            tool.name: tool
            for tool in [
                Tool(
                    "parse_subtitles",
                    "Read the .srt file of an Episode into Lines: number, "
                    "start and end in seconds, and text.",
                    {"episode": _EPISODE},
                    self._parse_subtitles,
                ),
                Tool(
                    "split_words",
                    "Reduce the text of one Line to its words: Base form, "
                    "word type and Seen form. Separable verbs are joined; "
                    "names, places and filler sounds are left out.",
                    {"text": {"type": "string", "description": "The text of a Line."}},
                    self._split_words,
                ),
                Tool(
                    "vocab_lookup",
                    "Give the word state (Known, Unknown, Taught, Excluded) of "
                    "each Base form, or null if it is not in the vocab store.",
                    {
                        "base_forms": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": 'Base forms, for example ["geben"].',
                        }
                    },
                    self._vocab_lookup,
                ),
                Tool(
                    "new_words",
                    "Process an Episode: list its New words (Base form and word "
                    "type), in the order they are first heard.",
                    {"episode": _EPISODE},
                    self._new_words,
                ),
                Tool(
                    "word_facts",
                    "Give the word facts of each word from the offline "
                    "Wiktionary data: meaning, gender, plural and verb forms "
                    "(present, past, participle, auxiliary). A noun compound "
                    "missing from the data is split into parts, with gender "
                    "and plural from its last part and no meaning. "
                    'meaning_status is "checked" for a meaning from the data '
                    'and "unchecked" for one an agent added.',
                    {
                        "words": {
                            "type": "array",
                            "items": _WORD,
                            "description": "Words as new_words gives them, for "
                            'example [{"base_form": "geben", "word_type": "VERB"}].',
                        }
                    },
                    self._word_facts,
                ),
                Tool(
                    "add_word_meaning",
                    "Store a short English meaning for a word that has no "
                    "meaning in the word facts data, for example a split "
                    'compound. It is marked "unchecked". A meaning from the '
                    "data cannot be replaced.",
                    {
                        "base_form": {"type": "string", "description": "The Base form."},
                        "meaning": {
                            "type": "string",
                            "description": 'A short English meaning, for example "homicide squad".',
                        },
                    },
                    self._add_word_meaning,
                ),
                Tool(
                    "pick_lesson_words",
                    "Pick the words the Lesson of an Episode teaches: up to 20 "
                    "Unknown words of the Episode, the most frequent first "
                    "(count from the subtitle frequency table; words not in the "
                    "table come last, with count null). Each word has the "
                    "Section (1, 2 or 3, for about 0-15, 15-30 and 30-45 "
                    "minutes) and the Line where it is first heard, and its "
                    "Seen form there. Use it after the Word Knowledge Check. "
                    "It changes no word state.",
                    {"episode": _EPISODE},
                    self._pick_lesson_words,
                ),
                Tool(
                    "open_page",
                    "Start the web server if it is not running and open the "
                    "exercise page of an Episode in the browser, on its Check tab.",
                    {"episode": _EPISODE},
                    self._open_page,
                ),
            ]
        }

    def call(self, name: str, arguments: dict):
        tool = self.tools.get(name)
        if tool is None:
            raise ToolError(f"Unknown tool {name!r}")
        tool.check(arguments)
        try:
            return tool.handler(**arguments)
        except (ValueError, PageError) as error:
            raise ToolError(str(error)) from error

    def _episode(self, name: str) -> Path:
        return find_episode(self._media_root, name)

    def _parse_subtitles(self, episode: str) -> list[dict]:
        return [
            _line(line) for line in read_lines(subtitle_file(self._episode(episode)))
        ]

    def _split_words(self, text: str) -> list[dict]:
        return [asdict(word) for word in analyse(text)]

    def _vocab_lookup(self, base_forms: list[str]) -> dict:
        with closing(VocabStore(self._db_path)) as store:
            states = {form: store.state_of(form) for form in base_forms}
        return {form: state and state.value for form, state in states.items()}

    def _new_words(self, episode: str) -> list[dict]:
        with closing(VocabStore(self._db_path)) as store:
            return [asdict(word) for word in new_words(self._episode(episode), store)]

    def _word_facts(self, words: list[dict]) -> list[dict]:
        with closing(WordFacts(self._facts_path)) as facts:
            return [
                asdict(facts.lookup(word["base_form"], word["word_type"]))
                for word in words
            ]

    def _add_word_meaning(self, base_form: str, meaning: str) -> dict:
        with closing(WordFacts(self._facts_path)) as facts:
            facts.add_meaning(base_form, meaning)
            return asdict(facts.lookup(base_form))

    def _pick_lesson_words(self, episode: str) -> list[dict]:
        folder = self._episode(episode)
        with (
            closing(FrequencyTable(self._frequency_path)) as frequency,
            closing(VocabStore(self._db_path)) as store,
        ):
            words = pick_lesson_words(folder, store, frequency)
        return [
            {
                "base_form": word.base_form,
                "word_type": word.word_type,
                "count": word.count,
                "section": word.section,
                "seen_form": word.seen_form,
                "line": _line(word.line),
            }
            for word in words
        ]

    def _open_page(self, episode: str) -> dict:
        return {"url": self._page.open(episode)}


def _line(line: Line) -> dict:
    return {
        "number": line.number,
        "start": line.start.total_seconds(),
        "end": line.end.total_seconds(),
        "text": line.text,
    }
