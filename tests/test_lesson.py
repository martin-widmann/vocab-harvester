"""The Lesson file: the agent writes it through write_lesson, the page reads it."""

import sqlite3
from contextlib import closing
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fakes import FakeClock, FakeDateClock, FakeLanguageTool

from core import (
    Curriculum,
    ExerciseStock,
    FoundTopic,
    FrequencyTable,
    GrammarPart,
    LessonExercise,
    LessonFiles,
    LessonInfo,
    SentenceChecker,
    SentenceToStore,
    Topic,
    VocabStore,
    WordFacts,
    add_sentences,
    build_frequency_table,
    check_answer,
    due_cards,
    finish_lesson,
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
    exercises=[
        LessonExercise("gap", "Ich helfe ___ Kind.", "dem", [], "helfen takes the dative."),
        LessonExercise(
            "choice", "Wir danken ___ Lehrerin.", "der", ["der", "die", "den"],
            "danken takes the dative.",
        ),
    ],
)
PASSIV = GrammarPart(
    topic_id="passiv-modalverb",
    example="Das Fenster muss repariert werden.",
    line=None,
    rule="Modal verb + past participle + werden at the end of the clause.",
    cases=["Die Arbeit kann morgen gemacht werden.", "Das darf nicht vergessen werden."],
    exercises=[
        LessonExercise(
            "gap", "Der Brief muss heute ___ werden.", "geschrieben", [],
            "Modal verb + participle + werden.",
        ),
        LessonExercise(
            "choice", "Das Auto kann morgen ___ werden.", "repariert",
            ["repariert", "reparieren"], "The participle comes before werden.",
        ),
    ],
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
    assert [
        (section["number"], section["start_minute"], section["end_minute"])
        for section in lesson["sections"]
    ] == [(1, 0, 15), (2, 15, 30), (3, 30, None)]
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
                "exercises": [
                    {
                        "id": "dativ:1",
                        "kind": "gap",
                        "sentence": "Ich helfe ___ Kind.",
                        "answer": "dem",
                        "options": [],
                        "explanation": "helfen takes the dative.",
                    },
                    {
                        "id": "dativ:2",
                        "kind": "choice",
                        "sentence": "Wir danken ___ Lehrerin.",
                        "answer": "der",
                        "options": ["der", "die", "den"],
                        "explanation": "danken takes the dative.",
                    },
                ],
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
                "exercises": [
                    {"id": "passiv-modalverb:1", **asdict(PASSIV.exercises[0])},
                    {"id": "passiv-modalverb:2", **asdict(PASSIV.exercises[1])},
                ],
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
        ([DATIV, replace(PASSIV, exercises=PASSIV.exercises[:1])], "2 to 4 exercises"),
        ([DATIV, replace(PASSIV, exercises=PASSIV.exercises * 3)], "2 to 4 exercises"),
        (
            [DATIV, replace(PASSIV, exercises=[
                PASSIV.exercises[0], replace(PASSIV.exercises[1], answer="gemacht"),
            ])],
            "answer must be one of the options",
        ),
        (
            [DATIV, replace(PASSIV, exercises=[
                PASSIV.exercises[0], replace(PASSIV.exercises[1], sentence="Kein Loch."),
            ])],
            "exactly one gap",
        ),
        (
            [DATIV, replace(PASSIV, exercises=[
                PASSIV.exercises[0], replace(PASSIV.exercises[1], kind="article"),
            ])],
            "kind must be one of gap, choice, sentence, translate, explain",
        ),
        (
            [DATIV, replace(PASSIV, exercises=[PASSIV.exercises[0]] * 2)],
            "twice",
        ),
    ],
    ids=[
        "topic not picked", "topic missing", "topic twice", "empty example",
        "two-line example", "long example", "empty rule", "one case",
        "empty case", "line without the topic", "line not in episode",
        "one exercise", "six exercises", "answer not an option", "no gap",
        "article kind", "exercise twice",
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
        (
            [replace(DATIV, exercises=[
                DATIV.exercises[0], replace(DATIV.exercises[1], sentence="Wir danken ___ Martha."),
            ]), PASSIV],
            "Martha",
        ),
        (
            [DATIV, replace(PASSIV, exercises=[
                PASSIV.exercises[0], replace(PASSIV.exercises[1], sentence="Er ___ nicht auf.", answer="gab", options=["gab", "gibt"]),
            ])],
            "is a Line of the Episode",
        ),
    ],
    ids=[
        "line not cut", "name in example", "name in a case", "name in the rule",
        "neutral example is a line", "case is a line", "name in an exercise",
        "exercise is a line",
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


def test_the_grammar_exercises_are_checked_by_languagetool_with_the_answer_in_the_gap(
    write, lessons, language_tool
):
    wrong = replace(PASSIV.exercises[0], sentence="Das ist ___ gemacht.", answer="falsch")
    with pytest.raises(ValueError, match="Fehler: falsch"):
        write(grammar=[DATIV, replace(PASSIV, exercises=[wrong, PASSIV.exercises[1]])])

    assert lessons.lessons() == []
    assert "Ich helfe dem Kind." in language_tool.texts[-1]


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


def test_an_episode_with_no_grammar_topics_gets_a_lesson_with_words_only(
    write, curriculum, stock, folder
):
    report_topics(curriculum, stock, EPISODE, read_lines(subtitle_file(folder)), [])

    lesson = write(grammar=[])

    assert [section["grammar"] for section in lesson["sections"]] == [[], [], []]
    assert words_of(lesson["sections"][0]) == ["suchen", "Höhle"]


def test_a_new_lesson_never_takes_the_number_of_an_unreadable_lesson_file(
    write, lessons, tmp_path
):
    (tmp_path / "lessons").mkdir()
    (tmp_path / "lessons" / "lesson-001.json").write_text("{not json", encoding="utf-8")

    lesson = write()

    assert lesson["number"] == 2
    assert (tmp_path / "lessons" / "lesson-001.json").read_text("utf-8") == "{not json"


def test_a_picked_topic_that_left_the_curriculum_must_be_reported_again(
    write, lessons, curriculum
):
    curriculum.approve(curriculum.propose([DRAFT[0], DRAFT[2]]).number)

    with pytest.raises(ValueError, match="'passiv-modalverb'.*report_topics"):
        write()

    assert lessons.lessons() == []


def test_a_line_that_left_the_subtitles_must_be_reported_again(write, lessons, folder):
    (folder / "episode.srt").unlink()
    folder.rmdir()
    write_episode(folder, LINES[:3])

    with pytest.raises(ValueError, match="no Line 4.*report_topics"):
        write()

    assert lessons.lessons() == []


def test_a_common_noun_spacy_takes_for_a_name_may_be_used(
    write, curriculum, stock, folder
):
    (folder / "episode.srt").unlink()
    folder.rmdir()
    write_episode(folder, [*LINES, (41, "Hund, komm her!")])

    lesson = write(grammar=[DATIV, replace(PASSIV, cases=["Der Hund muss gefüttert werden.", "Das darf nicht vergessen werden."])])

    assert lesson["sections"][2]["grammar"][0]["cases"][0] == "Der Hund muss gefüttert werden."


def test_a_new_write_keeps_the_words_of_the_lesson_after_they_are_taught(write, db):
    first = write()
    # What Finish does (a later ticket): the Lesson's words become Taught words.
    with closing(sqlite3.connect(db)) as raw, raw:
        raw.execute("UPDATE words SET state = 'Taught' WHERE state = 'Unknown'")

    again = write(grammar=[replace(DATIV, rule="Helfen takes the dative."), PASSIV])

    assert [words_of(s) for s in again["sections"]] == [
        words_of(s) for s in first["sections"]
    ]
    assert again["sections"][1]["grammar"][0]["rule"] == "Helfen takes the dative."


@pytest.mark.parametrize("name", ["Marthas", "Jonas'"])
def test_a_name_with_a_genitive_ending_is_a_name(write, name):
    with pytest.raises(ValueError, match="names from the Episode"):
        write(grammar=[replace(DATIV, example=f"{name} Bruder hilft ihm."), PASSIV])


def test_each_noun_with_a_gender_gets_a_der_die_das_exercise(write):
    lesson = write()

    (suchen, hoehle) = lesson["sections"][0]["words"]
    assert hoehle["exercises"] == [
        {
            "id": "Höhle:article",
            "kind": "article",
            "sentence": "___ Höhle",
            "answer": "die",
            "options": ["der", "die", "das"],
            "explanation": "Höhle is feminine: die Höhle.",
        }
    ]
    assert suchen["exercises"] == []


def test_a_lesson_with_answers_is_not_replaced(write, lessons):
    write()
    check_answer(lessons, 1, "Höhle:article", "die")

    with pytest.raises(ValueError, match="already has answers"):
        write(grammar=[PASSIV, replace(DATIV, rule="Helfen takes the dative.")])

    assert lessons.read(1)["sections"][1]["grammar"][0]["rule"] != "Helfen takes the dative."
    assert lessons.results(1)["answers"]["Höhle:article"]["right"] is True


TRANSLATE = LessonExercise(
    "translate", "We thank the teacher.", "Wir danken der Lehrerin.", [],
    "danken takes the dative.",
)
EXPLAIN = LessonExercise(
    "explain", "Ich folge dem Weg. Why dem and not den?",
    "folgen takes a dative object, and the dative of der Weg is dem Weg.",
    [], "folgen takes the dative.",
)
OWN_SENTENCE = LessonExercise(
    "sentence", "Write your own sentence with helfen.", "Ich helfe meiner Schwester.",
    [], "helfen takes the dative.",
)
OPEN_DATIV = replace(DATIV, exercises=[DATIV.exercises[0], TRANSLATE, EXPLAIN, OWN_SENTENCE])


def test_a_grammar_topic_may_have_open_exercises_the_grader_checks(write):
    lesson = write(grammar=[OPEN_DATIV, PASSIV])

    (dativ,) = lesson["sections"][1]["grammar"]
    assert [(exercise["id"], exercise["kind"]) for exercise in dativ["exercises"]] == [
        ("dativ:1", "gap"), ("dativ:2", "translate"), ("dativ:3", "explain"),
        ("dativ:4", "sentence"),
    ]
    assert dativ["exercises"][1] == {
        "id": "dativ:2",
        "kind": "translate",
        "sentence": "We thank the teacher.",
        "answer": "Wir danken der Lehrerin.",
        "options": [],
        "explanation": "danken takes the dative.",
    }


def test_the_german_answers_of_open_exercises_are_checked_by_languagetool(
    write, language_tool
):
    write(grammar=[OPEN_DATIV, PASSIV])

    checked = language_tool.texts[-1]
    assert "Wir danken der Lehrerin." in checked
    assert "Ich helfe meiner Schwester." in checked
    assert "Why dem and not den?" not in checked
    assert "We thank the teacher." not in checked


def test_a_wrong_german_answer_of_an_open_exercise_is_rejected(write, lessons):
    wrong = replace(TRANSLATE, answer="Wir danken falsch.")
    with pytest.raises(ValueError, match="Fehler: falsch"):
        write(grammar=[replace(DATIV, exercises=[DATIV.exercises[0], wrong]), PASSIV])

    assert lessons.lessons() == []


@pytest.mark.parametrize(
    "exercise, problem",
    [
        (replace(TRANSLATE, options=["a", "b"]), "has no options"),
        (replace(TRANSLATE, sentence="We thank ___ teacher."), "no gap"),
        (replace(OWN_SENTENCE, answer=" "), "answer is empty"),
        (replace(EXPLAIN, sentence=""), "sentence is empty"),
        (replace(EXPLAIN, explanation="Line one.\nLine two."), "one line"),
        (replace(TRANSLATE, sentence="We " * 120), "too long"),
        (replace(TRANSLATE, answer="Wir danken Martha."), "Martha"),
        (replace(TRANSLATE, answer="Er gab nicht auf."), "is a Line of the Episode"),
    ],
    ids=[
        "options", "gap", "empty answer", "empty task", "two-line explanation",
        "long task", "name", "episode line",
    ],
)
def test_write_lesson_rejects_a_malformed_open_exercise(write, lessons, exercise, problem):
    with pytest.raises(ValueError, match=problem):
        write(grammar=[replace(DATIV, exercises=[DATIV.exercises[0], exercise]), PASSIV])

    assert lessons.lessons() == []


def test_open_exercises_of_different_kinds_may_have_the_same_task(write):
    task = "Ich helfe dem Mann. Why dem?"
    explain = replace(EXPLAIN, sentence=task)
    sentence = replace(OWN_SENTENCE, sentence=task, answer="Ich helfe meiner Schwester.")

    write(grammar=[replace(DATIV, exercises=[DATIV.exercises[0], explain, sentence]), PASSIV])


def test_a_finished_lesson_gives_review_cards_with_the_episode_line_and_facts(
    write, lessons, store, curriculum
):
    write()
    finish_lesson(lessons, 1, store=store, curriculum=curriculum, today=date(2026, 11, 9))

    # The day after the Lesson: the Episode is watched.
    cards = {
        card.base_form: card
        for card in due_cards(store, FakeDateClock(datetime(2026, 11, 10, tzinfo=timezone.utc)))
    }

    assert set(cards) == UNKNOWN
    aufgeben = cards["aufgeben"]
    assert (aufgeben.seen_form, aufgeben.context) == ("gab auf", "Er **gab** nicht **auf**.")
    assert aufgeben.meaning == "to give up, to quit; to post (a letter)"
    assert aufgeben.needs_article is False
    hoehle = cards["Höhle"]
    assert hoehle.context == "Die Polizei sucht den Jungen in der **Höhle**."
    assert hoehle.needs_article is True


def test_writing_the_lesson_also_writes_its_tagged_subtitles(write, folder):
    write()

    tagged = [line.text for line in read_lines(folder / "episode.de.tagged.srt")]
    assert tagged[1] == "Martha hilft dem alten Mann im Garten. [helfen] [Dativ]"
    assert tagged[2] == "Er gab nicht auf. [aufgeben]"
    assert tagged[3].endswith("[Passiv mit Modalverb]")


def test_a_lesson_whose_tagged_subtitles_cannot_be_named_is_not_written(
    write, folder, lessons
):
    (folder / "episode.mkv").write_bytes(b"")
    (folder / "episode.mp4").write_bytes(b"")

    with pytest.raises(ValueError, match="one video"):
        write()

    assert lessons.lessons() == []
    assert not list(folder.glob("*.tagged.srt"))
