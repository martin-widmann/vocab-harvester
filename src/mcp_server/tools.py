"""The MCP tools. Each tool only calls the core and turns its answer into JSON."""

from collections.abc import Callable
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from core import (
    VocabStore,
    analyse,
    find_episode,
    new_words,
    read_lines,
    subtitle_file,
)
from web.launch import PageError

_EPISODE = {
    "type": "string",
    "description": 'The Episode name under the media folder, for example "Dark/S01E03".',
}

_JSON_TYPES = {"string": str, "array": list}


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
            schema = self.properties[key]
            if not isinstance(value, _JSON_TYPES[schema["type"]]):
                raise ToolError(f"{key} must be of type {schema['type']}")
            if schema["type"] == "array" and not all(
                isinstance(item, str) for item in value
            ):
                raise ToolError(f"{key} must be a list of strings")


class Toolbox:
    """The tools the agents can call. Each one is a thin call into the core."""

    def __init__(self, media_root: Path | str, db_path: Path | str, page: Page):
        self._media_root = Path(media_root)
        self._db_path = Path(db_path)
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
            {
                "number": line.number,
                "start": line.start.total_seconds(),
                "end": line.end.total_seconds(),
                "text": line.text,
            }
            for line in read_lines(subtitle_file(self._episode(episode)))
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

    def _open_page(self, episode: str) -> dict:
        return {"url": self._page.open(episode)}
