"""The Lesson file: the agent writes it through write_lesson, the page reads it."""

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from fakes import FakeClock, FakeLanguageTool

from core import (
    Curriculum,
    ExerciseStock,
    FoundTopic,
    FrequencyTable,
    GrammarPart,
    LessonFiles,
    LessonInfo,
    SentenceChecker,
    SentenceToStore,
    Topic,
    VocabStore,
    WordFacts,
    add_sentences,
    build_frequency_table,
    import_word_facts,
    new_words,
    read_lines,
    record_answer,
    report_topics,
    subtitle_file,
    write_lesson,
)

FIXTURES = Path(__file__).parent / "fixtures"
EPISODE = "Test/S01E01"

# One Line per (start minute, text): Section 1 is about 0-15 minutes,
# Section 2 about 15-30 and Section 3 after 30.
LINES = [
    (1, "Die Polizei sucht den Jungen in der Höhle."),
    (20, "Martha hilft dem alten Mann im Garten."),
    (35, "Er gab nicht auf."),
    (40, "Das muss sofort gemacht werden, sagt Jonas."),
]
UNKNOWN = {"Höhle", "suchen", "helfen", "aufgeben"}

DRAFT = [
    Topic("dativ", "Dativ", "A2"),
    Topic("passiv-modalverb", "Passiv mit Modalverb", "B2"),
    Topic("konjunktiv-1", "Konjunktiv I", "B2"),
]


def write_episode(folder: Path, lines: list[tuple[float, str]]) -> Path:
    blocks = []
    for number, (minute, text) in enumerate(lines, start=1):
        start = timedelta(minutes=minute)
        end = start + timedelta(seconds=2)
        blocks.append(f"{number}\n{_time(start)} --> {_time(end)}\n{text}\n")
    folder.mkdir(parents=True)
    (folder / "episode.srt").write_text("\n".join(blocks), encoding="utf-8")
    return folder


def _time(at: timedelta) -> str:
    seconds = int(at.total_seconds())
    return f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02},000"


@pytest.fixture
def folder(tmp_path):
    return write_episode(tmp_path / "media" / "Test" / "S01E01", LINES)


@pytest.fixture
def db(tmp_path):
    return tmp_path / "vocab.sqlite"


@pytest.fixture
def store(db, folder):
    store = VocabStore(db)
    for word in new_words(folder, store):
        record_answer(store, word, "U" if word.base_form in UNKNOWN else "K")
    yield store
    store.close()


@pytest.fixture
def frequency(tmp_path):
    path = tmp_path / "frequency.sqlite"
    with (FIXTURES / "frequency-sample.txt").open("rb") as source:
        build_frequency_table(source, path)
    table = FrequencyTable(path)
    yield table
    table.close()


@pytest.fixture
def facts(tmp_path):
    path = tmp_path / "word_facts.sqlite"
    with (FIXTURES / "kaikki-sample.jsonl").open("rb") as source:
        import_word_facts(source, path)
    facts = WordFacts(path)
    yield facts
    facts.close()


@pytest.fixture
def language_tool():
    return FakeLanguageTool()


@pytest.fixture
def checker(language_tool):
    return SentenceChecker(language_tool, FakeClock())


@pytest.fixture
def curriculum(db):
    curriculum = Curriculum(db)
    curriculum.approve(curriculum.propose(DRAFT).number)
    curriculum.review("dativ", passed=False)  # Dativ is now a Weak point.
    yield curriculum
    curriculum.close()


@pytest.fixture
def stock(db, curriculum, folder):
    stock = ExerciseStock(db)
    report_topics(
        curriculum,
        stock,
        EPISODE,
        read_lines(subtitle_file(folder)),
        [FoundTopic("dativ", [2]), FoundTopic("passiv-modalverb", [4])],
    )
    yield stock
    stock.close()


@pytest.fixture
def sentence_words():
    """The words the sentence-writer stored all 3 sentences for."""
    return UNKNOWN


@pytest.fixture
def sentences(store, checker, sentence_words):
    add_sentences(store, checker, [sentence(word, n) for word in sorted(sentence_words) for n in (1, 2, 3)])


def sentence(word: str, number: int, text: str | None = None) -> SentenceToStore:
    return SentenceToStore(word, number, text or f"Satz {number} mit dem Wort {word}.")


@pytest.fixture
def lessons(tmp_path):
    return LessonFiles(tmp_path / "lessons")


DATIV = GrammarPart(
    topic_id="dativ",
    example="Sie hilft dem alten Mann.",
    line=2,
    rule="Some verbs, such as helfen, danken and folgen, take a dative object.",
    cases=["Ich danke dir.", "Wir folgen dem Weg."],
)
PASSIV = GrammarPart(
    topic_id="passiv-modalverb",
    example="Das Fenster muss repariert werden.",
    line=None,
    rule="Modal verb + past participle + werden at the end of the clause.",
    cases=["Die Arbeit kann morgen gemacht werden.", "Das darf nicht vergessen werden."],
)


@pytest.fixture
def write(lessons, folder, store, frequency, facts, curriculum, stock, checker, sentences):
    def write(grammar=(DATIV, PASSIV), episode=EPISODE, episode_folder=folder):
        return write_lesson(
            lessons,
            episode,
            episode_folder,
            store=store,
            frequency=frequency,
            facts=facts,
            curriculum=curriculum,
            stock=stock,
            checker=checker,
            grammar=list(grammar),
        )

    return write


def words_of(section: dict) -> list[str]:
    return [word["base_form"] for word in section["words"]]


def test_the_lesson_has_3_sections_in_story_order_each_with_its_taught_words(write):
    lesson = write()

    assert lesson["episode"] == EPISODE
    assert [section["number"] for section in lesson["sections"]] == [1, 2, 3]
    assert [words_of(section) for section in lesson["sections"]] == [
        ["suchen", "Höhle"],
        ["helfen"],
        ["aufgeben"],
    ]


def test_words_have_their_facts_and_neutral_sentences_never_their_episode_line(write):
    lesson = write()

    (aufgeben,) = lesson["sections"][2]["words"]
    assert aufgeben["word_type"] == "VERB"
    assert aufgeben["seen_form"] == "gab auf"
    assert aufgeben["meaning"] == "to give up, to quit; to post (a letter)"
    assert aufgeben["meaning_status"] == "checked"
    assert aufgeben["sentences"] == [
        "Satz 1 mit dem Wort aufgeben.",
        "Satz 2 mit dem Wort aufgeben.",
        "Satz 3 mit dem Wort aufgeben.",
    ]
    texts = [
        str(value)
        for section in lesson["sections"]
        for word in section["words"]
        for value in word.values()
    ]
    for _, line in LINES:
        assert not any(line in text for text in texts)


def test_each_grammar_topic_goes_in_the_section_of_its_line_example_first_then_the_rule(
    write,
):
    lesson = write()

    assert [section["grammar"] for section in lesson["sections"]] == [
        [],
        [
            {
                "topic_id": "dativ",
                "name": "Dativ",
                "kind": "weak",
                "example": "Sie hilft dem alten Mann.",
                "line": 2,
                "lines": [2],
                "rule": DATIV.rule,
                "cases": DATIV.cases,
            }
        ],
        [
            {
                "topic_id": "passiv-modalverb",
                "name": "Passiv mit Modalverb",
                "kind": "new",
                "example": "Das Fenster muss repariert werden.",
                "line": None,
                "lines": [4],
                "rule": PASSIV.rule,
                "cases": PASSIV.cases,
            }
        ],
    ]


def test_a_lesson_is_numbered_and_listed_and_a_new_write_replaces_it(
    write, lessons, folder, curriculum, stock
):
    first = write()
    again = write(grammar=[PASSIV, replace(DATIV, rule="Helfen takes the dative.")])
    other = write_episode(folder.parent / "S01E02", LINES)
    report_topics(
        curriculum, stock, "Test/S01E02", read_lines(subtitle_file(other)),
        [FoundTopic("passiv-modalverb", [4])],
    )
    second = write(grammar=[PASSIV], episode="Test/S01E02", episode_folder=other)

    assert (first["number"], again["number"], second["number"]) == (1, 1, 2)
    assert lessons.lessons() == [
        LessonInfo(2, "Test/S01E02"),
        LessonInfo(1, EPISODE),
    ]
    assert lessons.read(1) == again
    assert lessons.read(1)["sections"][1]["grammar"][0]["rule"] == "Helfen takes the dative."
    assert lessons.read(2) == second


def test_a_lesson_that_is_not_written_cannot_be_read(lessons):
    with pytest.raises(ValueError, match="no Lesson 7"):
        lessons.read(7)


def test_an_unreadable_lesson_file_is_left_out_of_the_list(write, lessons, tmp_path):
    write()
    (tmp_path / "lessons" / "lesson-002.json").write_text("{not json", encoding="utf-8")

    assert lessons.lessons() == [LessonInfo(1, EPISODE)]
    with pytest.raises(ValueError, match="cannot be read"):
        lessons.read(2)


@pytest.mark.parametrize(
    "grammar, problem",
    [
        ([DATIV, replace(PASSIV, topic_id="konjunktiv-1")], "konjunktiv-1.*not a Grammar topic"),
        ([DATIV], "needs the Grammar topic 'passiv-modalverb'"),
        ([DATIV, DATIV, PASSIV], "twice"),
        ([DATIV, replace(PASSIV, example=" ")], "example is empty"),
        ([DATIV, replace(PASSIV, example="Das muss\nrepariert werden.")], "one line"),
        ([DATIV, replace(PASSIV, example="Das " * 100)], "too long"),
        ([DATIV, replace(PASSIV, rule="")], "rule is empty"),
        ([DATIV, replace(PASSIV, cases=["Das kann gemacht werden."])], "2 to 6 cases"),
        ([DATIV, replace(PASSIV, cases=["Das kann gemacht werden.", ""])], "case 2 is empty"),
        ([replace(DATIV, line=3), PASSIV], "Line 3 is not a Line"),
        ([replace(DATIV, line=99), PASSIV], "Line 99 is not a Line"),
    ],
    ids=[
        "topic not picked", "topic missing", "topic twice", "empty example",
        "two-line example", "long example", "empty rule", "one case",
        "empty case", "line without the topic", "line not in episode",
    ],
)
def test_write_lesson_rejects_a_lesson_that_does_not_match_the_schema(
    write, lessons, grammar, problem
):
    with pytest.raises(ValueError, match=problem):
        write(grammar=grammar)

    assert lessons.lessons() == []


@pytest.mark.parametrize(
    "grammar, problem",
    [
        (
            [replace(DATIV, example="Sie hilft dem alten Mann im Garten."), PASSIV],
            "cut it to the part",
        ),
        ([replace(DATIV, example="Martha hilft dem Mann."), PASSIV], "Martha"),
        ([replace(DATIV, cases=["Ich danke Jonas.", "Wir folgen dem Weg."]), PASSIV], "Jonas"),
        ([replace(DATIV, rule="Martha uses the dative."), PASSIV], "Martha"),
        ([DATIV, replace(PASSIV, example="Er gab nicht auf.")], "is a Line of the Episode"),
        (
            [DATIV, replace(PASSIV, cases=["Er gab nicht auf!", "Das darf nicht sein."])],
            "is a Line of the Episode",
        ),
    ],
    ids=[
        "line not cut", "name in example", "name in a case", "name in the rule",
        "neutral example is a line", "case is a line",
    ],
)
def test_an_episode_line_used_for_grammar_must_be_cut_with_its_names_changed(
    write, lessons, grammar, problem
):
    with pytest.raises(ValueError, match=problem):
        write(grammar=grammar)

    assert lessons.lessons() == []


def test_the_grammar_sentences_are_checked_by_languagetool(write, lessons, language_tool):
    with pytest.raises(ValueError, match="Fehler: falsch"):
        write(grammar=[DATIV, replace(PASSIV, cases=["Das ist falsch gemacht.", "Gut."])])

    assert lessons.lessons() == []
    assert "Das Fenster muss repariert werden." in language_tool.texts[-1]


def test_the_grammar_topics_must_be_reported_first(write, lessons):
    with pytest.raises(ValueError, match="report_topics"):
        write(episode="Test/S01E09")


@pytest.mark.parametrize("sentence_words", [UNKNOWN - {"helfen"}])
def test_each_word_needs_its_3_sentences_stored_first(write, lessons, store, checker):
    add_sentences(store, checker, [sentence("helfen", 1), sentence("helfen", 3)])

    with pytest.raises(ValueError, match="Sentence 2 of 'helfen'.*add_sentences"):
        write()

    assert lessons.lessons() == []


@pytest.mark.parametrize("sentence_words", [UNKNOWN - {"helfen"}])
def test_a_sentence_on_the_list_for_the_learner_is_left_out(write, store, checker):
    add_sentences(store, checker, [sentence("helfen", 1), sentence("helfen", 3)])
    for _ in range(4):
        add_sentences(store, checker, [sentence("helfen", 2, "Das ist falsch.")])

    lesson = write()

    (helfen,) = lesson["sections"][1]["words"]
    assert helfen["sentences"] == [
        "Satz 1 mit dem Wort helfen.",
        "Satz 3 mit dem Wort helfen.",
    ]
