from pathlib import Path

import pytest
from fakes import FakeClock, FakeLanguageTool

from core import VocabStore, WordState, build_frequency_table, import_word_facts
from core.language_tool import LanguageToolError
from mcp_server.tools import ToolError, Toolbox

MEDIA = Path(__file__).parent / "fixtures"
KAIKKI_SAMPLE = MEDIA / "kaikki-sample.jsonl"
FREQUENCY_SAMPLE = MEDIA / "frequency-sample.txt"


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
def facts(tmp_path):
    path = tmp_path / "word_facts.sqlite"
    with KAIKKI_SAMPLE.open("rb") as source:
        import_word_facts(source, path)
    return path


@pytest.fixture
def frequency(tmp_path):
    path = tmp_path / "frequency.sqlite"
    with FREQUENCY_SAMPLE.open("rb") as source:
        build_frequency_table(source, path)
    return path


@pytest.fixture
def language_tool():
    return FakeLanguageTool()


@pytest.fixture
def toolbox(db, page, facts, frequency, language_tool):
    return Toolbox(
        media_root=MEDIA,
        db_path=db,
        page=page,
        facts_path=facts,
        frequency_path=frequency,
        language_tool=language_tool,
        clock=FakeClock(),
    )


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


def test_word_facts_tool_gives_the_facts_of_each_word_from_the_data(toolbox):
    facts = toolbox.call(
        "word_facts",
        {
            "words": [
                {"base_form": "aufgeben", "word_type": "VERB"},
                {"base_form": "Mordkommission", "word_type": "NOUN"},
            ]
        },
    )

    assert facts == [
        {
            "base_form": "aufgeben",
            "meaning": "to give up, to quit; to post (a letter)",
            "meaning_status": "checked",
            "gender": None,
            "plural": None,
            "verb_forms": {
                "present": "gibt auf",
                "past": "gab auf",
                "participle": "aufgegeben",
                "auxiliary": "haben",
            },
            "parts": [],
        },
        {
            "base_form": "Mordkommission",
            "meaning": None,
            "meaning_status": None,
            "gender": "feminine",
            "plural": "Mordkommissionen",
            "verb_forms": None,
            "parts": ["Mord", "Kommission"],
        },
    ]


@pytest.mark.parametrize(
    "words",
    [
        ["Hund"],
        [{"base_form": "Hund"}],
        [{"base_form": "Hund", "word_type": 1}],
        [{"base_form": "Hund", "word_type": "NOUN", "extra": "x"}],
    ],
)
def test_word_facts_tool_rejects_words_that_are_not_base_form_and_word_type(
    toolbox, words
):
    with pytest.raises(ToolError, match="words"):
        toolbox.call("word_facts", {"words": words})


def test_add_word_meaning_tool_stores_an_agent_meaning_marked_unchecked(toolbox):
    result = toolbox.call(
        "add_word_meaning", {"base_form": "Mordkommission", "meaning": "homicide squad"}
    )

    assert result["meaning"] == "homicide squad"
    assert result["meaning_status"] == "unchecked"
    [facts] = toolbox.call(
        "word_facts", {"words": [{"base_form": "Mordkommission", "word_type": "NOUN"}]}
    )
    assert (facts["meaning"], facts["meaning_status"]) == ("homicide squad", "unchecked")


def test_add_word_meaning_tool_cannot_replace_a_meaning_from_the_data(toolbox):
    with pytest.raises(ToolError, match="word facts data"):
        toolbox.call("add_word_meaning", {"base_form": "Hund", "meaning": "cat"})


def test_word_facts_tool_without_imported_data_is_a_tool_error(db, page, tmp_path):
    toolbox = Toolbox(MEDIA, db, page, facts_path=tmp_path / "missing.sqlite")

    with pytest.raises(ToolError, match="import-word-facts"):
        toolbox.call("word_facts", {"words": [{"base_form": "Hund", "word_type": "NOUN"}]})


def test_pick_lesson_words_tool_gives_the_unknown_words_most_frequent_first(toolbox, db):
    store = VocabStore(db)
    store.add("aufgeben", "VERB", WordState.UNKNOWN)
    store.add("suchen", "VERB", WordState.UNKNOWN)
    store.add("Polizei", "NOUN", WordState.KNOWN)

    words = toolbox.call("pick_lesson_words", {"episode": "Dark/S01E01"})

    assert words == [
        {
            "base_form": "suchen",
            "word_type": "VERB",
            "count": 70,
            "section": 1,
            "seen_form": "sucht",
            "line": {
                "number": 2,
                "start": 4.0,
                "end": 6.2,
                "text": "<i>Die Polizei sucht\nden Jungen in der Höhle.</i>",
            },
        },
        {
            "base_form": "aufgeben",
            "word_type": "VERB",
            "count": None,
            "section": 1,
            "seen_form": "gab auf",
            "line": {"number": 3, "start": 7.1, "end": 9.0, "text": "Er gab nicht auf."},
        },
    ]
    assert store.state_of("aufgeben") == WordState.UNKNOWN


def test_pick_lesson_words_tool_without_a_frequency_table_is_a_tool_error(
    db, page, facts, tmp_path
):
    toolbox = Toolbox(
        MEDIA, db, page, facts_path=facts, frequency_path=tmp_path / "missing.sqlite"
    )

    with pytest.raises(ToolError, match="build-frequency"):
        toolbox.call("pick_lesson_words", {"episode": "Dark/S01E01"})


def test_add_sentences_tool_stores_the_sentences_languagetool_passes(toolbox, db):
    VocabStore(db).add("aufgeben", "VERB", WordState.UNKNOWN)

    results = toolbox.call(
        "add_sentences",
        {
            "sentences": [
                {"base_form": "aufgeben", "number": 1, "sentence": "Er gibt nie auf."},
                {"base_form": "aufgeben", "number": 2, "sentence": "Das ist falsch."},
            ]
        },
    )

    assert results == [
        {
            "base_form": "aufgeben",
            "number": 1,
            "sentence": "Er gibt nie auf.",
            "status": "stored",
            "problems": [],
            "retries_left": 0,
        },
        {
            "base_form": "aufgeben",
            "number": 2,
            "sentence": "Das ist falsch.",
            "status": "retry",
            "problems": ["Fehler: falsch"],
            "retries_left": 3,
        },
    ]
    assert VocabStore(db).example_sentences("aufgeben") == {1: "Er gibt nie auf."}


def test_failed_sentences_tool_gives_the_list_for_the_learner(toolbox, db):
    VocabStore(db).add("aufgeben", "VERB", WordState.UNKNOWN)
    for _ in range(4):
        toolbox.call(
            "add_sentences",
            {"sentences": [{"base_form": "aufgeben", "number": 3, "sentence": "falsch"}]},
        )

    assert toolbox.call("failed_sentences", {}) == [
        {
            "base_form": "aufgeben",
            "number": 3,
            "sentence": "falsch",
            "problems": ["Fehler: falsch"],
        }
    ]


@pytest.mark.parametrize("number", ["1", 1.0, True])
def test_add_sentences_tool_needs_a_whole_number(toolbox, db, number):
    VocabStore(db).add("aufgeben", "VERB", WordState.UNKNOWN)

    with pytest.raises(ToolError, match="integer"):
        toolbox.call(
            "add_sentences",
            {"sentences": [{"base_form": "aufgeben", "number": number, "sentence": "Gut."}]},
        )


def test_add_sentences_tool_for_a_word_that_is_not_unknown_is_a_tool_error(toolbox):
    with pytest.raises(ToolError, match="not an Unknown or Taught word"):
        toolbox.call(
            "add_sentences",
            {"sentences": [{"base_form": "Polizei", "number": 1, "sentence": "Gut."}]},
        )


def test_add_sentences_tool_when_languagetool_fails_is_a_tool_error(
    toolbox, db, language_tool
):
    VocabStore(db).add("aufgeben", "VERB", WordState.UNKNOWN)

    def no_network(text):
        raise LanguageToolError("LanguageTool cannot be reached")

    language_tool.check = no_network

    with pytest.raises(ToolError, match="cannot be reached"):
        toolbox.call(
            "add_sentences",
            {"sentences": [{"base_form": "aufgeben", "number": 1, "sentence": "Gut."}]},
        )
    assert VocabStore(db).example_sentences("aufgeben") == {}
