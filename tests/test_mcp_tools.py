from pathlib import Path

import pytest

from core import VocabStore, WordState
from mcp_server.tools import ToolError, Toolbox

MEDIA = Path(__file__).parent / "fixtures"


@pytest.fixture
def db(tmp_path):
    return tmp_path / "vocab.sqlite"


class FakePage:
    def __init__(self):
        self.opened: list[str] = []

    def open(self, episode: str) -> str:
        self.opened.append(episode)
        return f"http://127.0.0.1:8000/?episode={episode}"


@pytest.fixture
def page():
    return FakePage()


@pytest.fixture
def toolbox(db, page):
    return Toolbox(media_root=MEDIA, db_path=db, page=page)


def test_new_words_tool_lists_the_new_words_of_an_episode_by_name(toolbox, db):
    VocabStore(db).add("Polizei", "NOUN", WordState.KNOWN)

    words = toolbox.call("new_words", {"episode": "Dark/S01E01"})

    assert {"base_form": "aufgeben", "word_type": "VERB"} in words
    assert {"base_form": "Höhle", "word_type": "NOUN"} in words
    assert {"base_form": "Polizei", "word_type": "NOUN"} not in words


@pytest.mark.parametrize("episode", ["Dark/S09E09", "../.."])
def test_an_episode_that_is_not_in_the_media_folder_is_a_tool_error(toolbox, episode):
    with pytest.raises(ToolError, match="No Episode"):
        toolbox.call("new_words", {"episode": episode})


def test_parse_subtitles_tool_gives_the_lines_of_an_episode_with_times_in_seconds(toolbox):
    lines = toolbox.call("parse_subtitles", {"episode": "Dark/S01E01"})

    assert lines[0] == {
        "number": 1,
        "start": 1.0,
        "end": 3.5,
        "text": "Äh, wo ist Mikkel?",
    }
    assert len(lines) == 4


def test_split_words_tool_gives_base_form_word_type_and_seen_form(toolbox):
    words = toolbox.call("split_words", {"text": "Er gab nicht auf."})

    assert {"base_form": "aufgeben", "word_type": "VERB", "seen_form": "gab auf"} in words


def test_vocab_lookup_tool_gives_the_word_state_or_none_for_each_base_form(toolbox, db):
    VocabStore(db).add("Polizei", "NOUN", WordState.KNOWN)
    VocabStore(db).add("Höhle", "NOUN", WordState.EXCLUDED)

    states = toolbox.call(
        "vocab_lookup", {"base_forms": ["Polizei", "Höhle", "aufgeben"]}
    )

    assert states == {"Polizei": "Known", "Höhle": "Excluded", "aufgeben": None}


@pytest.mark.parametrize("arguments", [{}, {"episode": "Dark/S01E01", "extra": 1}])
def test_wrong_arguments_are_a_tool_error(toolbox, arguments):
    with pytest.raises(ToolError):
        toolbox.call("new_words", arguments)


def test_an_unknown_tool_is_a_tool_error(toolbox):
    with pytest.raises(ToolError, match="Unknown tool"):
        toolbox.call("delete_everything", {})


def test_an_argument_of_the_wrong_type_is_a_tool_error(toolbox):
    with pytest.raises(ToolError):
        toolbox.call("vocab_lookup", {"base_forms": "Polizei"})


def test_open_page_tool_opens_the_exercise_page_of_an_episode(toolbox, page):
    result = toolbox.call("open_page", {"episode": "Dark/S01E01"})

    assert page.opened == ["Dark/S01E01"]
    assert result == {"url": "http://127.0.0.1:8000/?episode=Dark/S01E01"}
