"""The MCP tools. Each tool only calls the core and turns its answer into JSON."""

from collections.abc import Callable
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from core import (
    Curriculum,
    FrequencyTable,
    Line,
    SentenceChecker,
    SentenceToStore,
    Topic,
    TopicStatus,
    VocabStore,
    WordFacts,
    add_sentences,
    analyse,
    curriculum_gaps,
    failed_sentences,
    find_episode,
    new_words,
    pick_lesson_words,
    read_lines,
    subtitle_file,
)
from core.frequency import DEFAULT_FREQUENCY
from core.language_tool import LanguageTool, SystemClock
from core.sentences import Clock, LanguageToolApi
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

_SENTENCE = {
    "type": "object",
    "properties": {
        "base_form": {"type": "string"},
        "number": {"type": "integer", "minimum": 1, "maximum": 3},
        "sentence": {"type": "string"},
    },
    "required": ["base_form", "number", "sentence"],
    "additionalProperties": False,
}

_TOPIC = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "level": {"type": "string"},
    },
    "required": ["id", "name", "level"],
    "additionalProperties": False,
}

_JSON_TYPES = {"string": str, "integer": int, "array": list, "object": dict}


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
    if not isinstance(value, _JSON_TYPES[schema["type"]]) or isinstance(value, bool):
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
        language_tool: LanguageToolApi | None = None,
        clock: Clock | None = None,
    ):
        self._media_root = Path(media_root)
        self._db_path = Path(db_path)
        self._facts_path = Path(facts_path)
        self._frequency_path = Path(frequency_path)
        self._page = page
        # One checker for the whole session, so the rate limit holds across calls.
        self._checker = SentenceChecker(
            language_tool or LanguageTool(), clock or SystemClock()
        )
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
                    "add_sentences",
                    "Store example sentences for Unknown or Taught words: "
                    "sentence 1, 2 and 3 of each Base form. LanguageTool checks "
                    "every sentence first; only a sentence with no problems is "
                    "stored. Send all sentences in one call. Each result has a "
                    'status: "stored"; "retry" (it failed: write a new sentence '
                    "with the same number, retries_left tells how many tries "
                    'are left); or "listed" (it failed its last retry and is on '
                    "the list for the learner; it takes no more tries). "
                    "problems gives what LanguageTool found.",
                    {
                        "sentences": {
                            "type": "array",
                            "items": _SENTENCE,
                            "description": 'For example [{"base_form": "aufgeben", '
                            '"number": 1, "sentence": "Er gibt nie auf."}].',
                        }
                    },
                    self._add_sentences,
                ),
                Tool(
                    "failed_sentences",
                    "Give the list for the learner: example sentences whose "
                    "last LanguageTool check failed, with the problems found. "
                    'Status "listed": it failed all its retries. Status '
                    '"retry": it has retries left, but no new sentence was sent. '
                    "None of them is stored.",
                    {},
                    self._failed_sentences,
                ),
                Tool(
                    "curriculum",
                    "Give the Curriculum: each Grammar topic in order, with its "
                    "Topic state (Not seen, Seen, Learned, Solid) and whether it "
                    "is a Weak point. Also give the open proposal that waits for "
                    "the learner's approval, or null.",
                    {},
                    self._curriculum,
                ),
                Tool(
                    "propose_curriculum",
                    "Propose a full Curriculum: the first draft or a change. It "
                    "is NOT stored as the Curriculum; it waits for the learner's "
                    "approval, and replaces an older open proposal. Send every "
                    "topic, in teaching order, with an id (lowercase, hyphens, "
                    'for example "konjunktiv-2"), the name a Tag shows (for '
                    'example "Konjunktiv II") and its level (A1, A2, B1, B2, C1 '
                    "or C2). On approval, a kept topic keeps its Topic state; an "
                    "added topic starts as Solid up to B1, else as Not seen; a "
                    "removed topic loses its Topic state. The result gives the "
                    "proposal number and the ids it adds and removes.",
                    {
                        "topics": {
                            "type": "array",
                            "items": _TOPIC,
                            "description": 'For example [{"id": "dativ", '
                            '"name": "Dativ", "level": "A2"}].',
                        }
                    },
                    self._propose_curriculum,
                ),
                Tool(
                    "approve_curriculum",
                    "Store the open proposal as the Curriculum. Call it ONLY "
                    "after you showed the learner this proposal and the learner "
                    "said yes to it in the chat. Never call it on your own.",
                    {
                        "proposal": {
                            "type": "integer",
                            "description": "The number of the proposal the learner approved.",
                        }
                    },
                    self._approve_curriculum,
                ),
                Tool(
                    "curriculum_gaps",
                    "Pick the 2 Grammar topics a Lesson teaches, from the topics "
                    "found in its Episode: new is the first Not seen topic in "
                    "Curriculum order, weak is the Weak point that has been weak "
                    "the longest. Either is null when the Episode has none. "
                    "not_in_curriculum names found topic ids the Curriculum does "
                    "not have (propose a change if they belong in it).",
                    {
                        "found_topics": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Ids of the Curriculum topics found in "
                            "the Episode's Lines, for example "
                            '["dativ", "konjunktiv-1"].',
                        }
                    },
                    self._curriculum_gaps,
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

    def _add_sentences(self, sentences: list[dict]) -> list[dict]:
        with closing(VocabStore(self._db_path)) as store:
            results = add_sentences(
                store,
                self._checker,
                [SentenceToStore(**sentence) for sentence in sentences],
            )
        return [asdict(result) for result in results]

    def _failed_sentences(self) -> list[dict]:
        with closing(VocabStore(self._db_path)) as store:
            return [asdict(failed) for failed in failed_sentences(store)]

    def _curriculum(self) -> dict:
        with closing(Curriculum(self._db_path)) as curriculum:
            proposal = curriculum.proposal()
            return {
                "topics": [_topic_status(status) for status in curriculum.topics()],
                "proposal": proposal and asdict(proposal),
            }

    def _propose_curriculum(self, topics: list[dict]) -> dict:
        with closing(Curriculum(self._db_path)) as curriculum:
            return asdict(curriculum.propose([Topic(**topic) for topic in topics]))

    def _approve_curriculum(self, proposal: int) -> list[dict]:
        with closing(Curriculum(self._db_path)) as curriculum:
            return [_topic_status(status) for status in curriculum.approve(proposal)]

    def _curriculum_gaps(self, found_topics: list[str]) -> dict:
        with closing(Curriculum(self._db_path)) as curriculum:
            return asdict(curriculum_gaps(curriculum, found_topics))

    def _open_page(self, episode: str) -> dict:
        return {"url": self._page.open(episode)}


def _line(line: Line) -> dict:
    return {
        "number": line.number,
        "start": line.start.total_seconds(),
        "end": line.end.total_seconds(),
        "text": line.text,
    }


def _topic_status(status: TopicStatus) -> dict:
    return {**asdict(status.topic), "state": status.state.value, "weak": status.weak}
