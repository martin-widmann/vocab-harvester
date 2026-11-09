"""Check the fixed answers of a Lesson and Finish it."""

import json
from datetime import date, datetime, timezone

import pytest
from fakes import FakeDateClock

from core import (
    Curriculum,
    LessonFiles,
    Result,
    Topic,
    TopicResult,
    TopicState,
    VocabStore,
    WordState,
    check_answer,
    due_cards,
    finish_lesson,
    lesson_for_page,
)


def exercise(id, kind, sentence, answer, options, explanation):
    return {
        "id": id,
        "kind": kind,
        "sentence": sentence,
        "answer": answer,
        "options": options,
        "explanation": explanation,
    }


HOEHLE = exercise(
    "Höhle:article", "article", "___ Höhle", "die", ["der", "die", "das"],
    "Höhle is feminine: die Höhle.",
)
DATIV = [
    exercise("dativ:1", "gap", "Ich helfe ___ Kind.", "dem", [], "helfen takes the dative."),
    exercise(
        "dativ:2", "choice", "Wir danken ___ Lehrerin.", "der", ["der", "die", "den"],
        "danken takes the dative.",
    ),
]
PASSIV = [
    exercise(
        f"passiv-modalverb:{n}", "gap", sentence, answer, [], "Modal verb + participle + werden."
    )
    for n, (sentence, answer) in enumerate(
        [
            ("Der Brief muss heute ___ werden.", "geschrieben"),
            ("Das Auto kann morgen ___ werden.", "repariert"),
            ("Die Tür darf nicht ___ werden.", "geöffnet"),
        ],
        start=1,
    )
]


def word(base_form, word_type, exercises=()):
    return {"base_form": base_form, "word_type": word_type, "exercises": list(exercises)}


def topic(topic_id, kind, exercises):
    return {"topic_id": topic_id, "kind": kind, "exercises": exercises}


LESSON = {
    "schema_version": 1,
    "number": 1,
    "episode": "Test/S01E01",
    "sections": [
        {"number": 1, "words": [word("suchen", "VERB"), word("Höhle", "NOUN", [HOEHLE])], "grammar": []},
        {"number": 2, "words": [word("helfen", "VERB")], "grammar": [topic("dativ", "weak", DATIV)]},
        {
            "number": 3,
            "words": [word("aufgeben", "VERB")],
            "grammar": [topic("passiv-modalverb", "new", PASSIV)],
        },
    ],
}

TODAY = date(2026, 11, 9)

TOPICS = [
    Topic("dativ", "Dativ", "A2"),
    Topic("passiv-modalverb", "Passiv mit Modalverb", "B2"),
    Topic("konjunktiv-1", "Konjunktiv I", "B2"),
]


@pytest.fixture
def lessons(tmp_path):
    folder = tmp_path / "lessons"
    folder.mkdir()
    (folder / "lesson-001.json").write_text(json.dumps(LESSON), encoding="utf-8")
    return LessonFiles(folder)


@pytest.fixture
def db(tmp_path):
    return tmp_path / "vocab.sqlite"


@pytest.fixture
def store(db):
    store = VocabStore(db)
    for base_form, word_type in [
        ("suchen", "VERB"), ("Höhle", "NOUN"), ("helfen", "VERB"), ("aufgeben", "VERB"),
    ]:
        store.add(base_form, word_type, WordState.UNKNOWN)
    store.add("Hund", "NOUN", WordState.UNKNOWN)  # Not in this Lesson.
    yield store
    store.close()


@pytest.fixture
def curriculum(db):
    curriculum = Curriculum(db)
    curriculum.approve(curriculum.propose(TOPICS).number)
    curriculum.review("dativ", passed=False)  # Dativ is a Weak point: Learned.
    yield curriculum
    curriculum.close()


def test_finish_teaches_each_word_with_the_facts_of_its_lesson(
    tmp_path, lessons, store, curriculum
):
    path = tmp_path / "lessons" / "lesson-001.json"
    lesson = json.loads(path.read_text(encoding="utf-8"))
    lesson["sections"][0]["words"][1].update(
        seen_form="Höhle", meaning="cave", gender="feminine"
    )
    path.write_text(json.dumps(lesson), encoding="utf-8")

    finish_lesson(lessons, 1, store=store, curriculum=curriculum, today=TODAY)

    cards = {
        card.base_form: card
        for card in due_cards(store, FakeDateClock(datetime(2026, 11, 10, tzinfo=timezone.utc)))
    }
    assert set(cards) == {"suchen", "Höhle", "helfen", "aufgeben"}
    assert (cards["Höhle"].seen_form, cards["Höhle"].meaning) == ("Höhle", "cave")
    assert cards["Höhle"].needs_article is True
    # Taught today: no card before the next day.
    assert due_cards(store, FakeDateClock(datetime(2026, 11, 9, 23, tzinfo=timezone.utc))) == []


def test_a_right_gap_answer_gives_right_the_correction_and_a_short_reason(lessons):
    assert check_answer(lessons, 1, "dativ:1", "dem") == Result(
        right=True, correction="Ich helfe dem Kind.", reason="helfen takes the dative."
    )


def test_a_wrong_gap_answer_gives_wrong_with_the_correction(lessons):
    assert check_answer(lessons, 1, "dativ:1", "den") == Result(
        right=False, correction="Ich helfe dem Kind.", reason="helfen takes the dative."
    )


@pytest.mark.parametrize("answer", ["  dem ", "Dem"])
def test_a_gap_answer_may_differ_in_outer_spaces_and_case(lessons, answer):
    assert check_answer(lessons, 1, "dativ:1", answer).right


def test_a_gap_answer_must_have_the_right_letters(lessons):
    assert not check_answer(lessons, 1, "passiv-modalverb:3", "geoffnet").right


def test_a_pick_one_answer_is_right_only_for_the_answer_option(lessons):
    assert check_answer(lessons, 1, "dativ:2", "der").right
    assert not check_answer(lessons, 1, "passiv-modalverb:1", "geschreiben").right


def test_a_pick_one_answer_that_is_not_an_option_is_rejected(lessons):
    with pytest.raises(ValueError, match="one of der, die, den"):
        check_answer(lessons, 1, "dativ:2", "dem")

    assert lessons.results(1)["answers"] == {}


def test_an_article_answer_is_checked_with_the_gender_of_the_noun(lessons):
    assert check_answer(lessons, 1, "Höhle:article", "der") == Result(
        right=False, correction="die Höhle", reason="Höhle is feminine: die Höhle."
    )


def test_an_article_answer_may_start_with_a_capital_letter(lessons):
    assert check_answer(lessons, 1, "Höhle:article", "Die").right


def test_an_article_answer_that_is_not_der_die_or_das_is_rejected(lessons):
    with pytest.raises(ValueError, match="der, die or das"):
        check_answer(lessons, 1, "Höhle:article", "dies")


def test_an_exercise_that_the_lesson_does_not_have_is_rejected(lessons):
    with pytest.raises(ValueError, match="no exercise 'dativ:9'"):
        check_answer(lessons, 1, "dativ:9", "dem")
    with pytest.raises(ValueError, match="no Lesson 2"):
        check_answer(lessons, 2, "dativ:1", "dem")


def test_answers_and_results_are_saved_to_the_results_file(lessons, tmp_path):
    check_answer(lessons, 1, "dativ:1", "den")
    check_answer(lessons, 1, "Höhle:article", "die")

    saved = json.loads(
        (tmp_path / "lessons" / "lesson-001.results.json").read_text(encoding="utf-8")
    )
    assert saved == {
        "schema_version": 1,
        "lesson": 1,
        "episode": "Test/S01E01",
        "answers": {
            "dativ:1": {
                "answer": "den",
                "right": False,
                "correction": "Ich helfe dem Kind.",
                "reason": "helfen takes the dative.",
            },
            "Höhle:article": {
                "answer": "die",
                "right": True,
                "correction": "die Höhle",
                "reason": "Höhle is feminine: die Höhle.",
            },
        },
        "finished": False,
    }
    assert lessons.results(1) == saved


def test_the_first_answer_to_an_exercise_stands(lessons):
    first = check_answer(lessons, 1, "dativ:1", "den")

    assert check_answer(lessons, 1, "dativ:1", "dem") == first
    assert lessons.results(1)["answers"]["dativ:1"]["answer"] == "den"


def test_a_lesson_with_no_answers_has_empty_results(lessons):
    assert lessons.results(1) == {
        "schema_version": 1,
        "lesson": 1,
        "episode": "Test/S01E01",
        "answers": {},
        "finished": False,
    }


def answer_all(lessons, right_ids):
    """Answer every exercise: right for the ids given, wrong for the others."""
    for item in [HOEHLE, *DATIV, *PASSIV]:
        if item["kind"] == "gap":
            wrong = "xxx"
        else:
            wrong = next(option for option in item["options"] if option != item["answer"])
        check_answer(lessons, 1, item["id"], item["answer"] if item["id"] in right_ids else wrong)


def states(curriculum):
    return {status.topic.id: status.state for status in curriculum.topics()}


def test_finish_makes_the_lesson_words_taught_words_at_once(lessons, store, curriculum):
    finished = finish_lesson(lessons, 1, store=store, curriculum=curriculum, today=TODAY)

    assert finished.taught_words == ["suchen", "Höhle", "helfen", "aufgeben"]
    for base_form in finished.taught_words:
        assert store.state_of(base_form) == WordState.TAUGHT
    assert store.state_of("Hund") == WordState.UNKNOWN


def test_finish_leaves_a_lesson_word_that_is_no_longer_unknown(lessons, store, curriculum):
    store.set_state("helfen", WordState.KNOWN)

    finished = finish_lesson(lessons, 1, store=store, curriculum=curriculum, today=TODAY)

    assert "helfen" not in finished.taught_words
    assert store.state_of("helfen") == WordState.KNOWN


def test_a_new_topic_whose_exercises_passed_becomes_learned(lessons, store, curriculum):
    answer_all(lessons, {"passiv-modalverb:1", "passiv-modalverb:2"})

    finished = finish_lesson(lessons, 1, store=store, curriculum=curriculum, today=TODAY)

    assert states(curriculum)["passiv-modalverb"] == TopicState.LEARNED
    assert TopicResult("passiv-modalverb", 2, 3, True, TopicState.LEARNED) in finished.topics


def test_a_new_topic_whose_exercises_failed_becomes_seen(lessons, store, curriculum):
    answer_all(lessons, {"passiv-modalverb:1"})

    finished = finish_lesson(lessons, 1, store=store, curriculum=curriculum, today=TODAY)

    assert states(curriculum)["passiv-modalverb"] == TopicState.SEEN
    assert TopicResult("passiv-modalverb", 1, 3, False, TopicState.SEEN) in finished.topics


def test_an_exercise_with_no_answer_counts_as_wrong(lessons, store, curriculum):
    check_answer(lessons, 1, "passiv-modalverb:1", "geschrieben")

    finish_lesson(lessons, 1, store=store, curriculum=curriculum, today=TODAY)

    assert states(curriculum)["passiv-modalverb"] == TopicState.SEEN


def test_a_weak_point_the_lesson_taught_again_stays_learned_and_weak(
    lessons, store, curriculum
):
    answer_all(lessons, {"dativ:1", "dativ:2"})

    finish_lesson(lessons, 1, store=store, curriculum=curriculum, today=TODAY)

    (dativ,) = [status for status in curriculum.topics() if status.topic.id == "dativ"]
    assert (dativ.state, dativ.weak) == (TopicState.LEARNED, True)
    assert states(curriculum)["konjunktiv-1"] == TopicState.NOT_SEEN


def test_finish_is_saved_in_the_results_file_and_ends_the_answers(
    lessons, store, curriculum
):
    check_answer(lessons, 1, "dativ:1", "den")

    finish_lesson(lessons, 1, store=store, curriculum=curriculum, today=TODAY)

    assert lessons.results(1)["finished"] is True
    assert not check_answer(lessons, 1, "dativ:1", "dem").right
    with pytest.raises(ValueError, match="finished"):
        check_answer(lessons, 1, "dativ:2", "der")
    with pytest.raises(ValueError, match="already finished"):
        finish_lesson(lessons, 1, store=store, curriculum=curriculum, today=TODAY)


def test_a_topic_that_left_the_curriculum_is_left_out(lessons, store, curriculum):
    curriculum.approve(curriculum.propose([TOPICS[0], TOPICS[2]]).number)

    finished = finish_lesson(lessons, 1, store=store, curriculum=curriculum, today=TODAY)

    assert [result.topic_id for result in finished.topics] == ["dativ"]
    assert lessons.results(1)["finished"] is True


def test_the_page_gets_the_lesson_without_answers_and_with_the_saved_results(lessons):
    check_answer(lessons, 1, "dativ:1", "den")

    shown = lesson_for_page(lessons, 1)

    exercises = [
        item
        for section in shown["sections"]
        for part in [*section["words"], *section["grammar"]]
        for item in part["exercises"]
    ]
    assert [item["id"] for item in exercises] == [
        "Höhle:article", "dativ:1", "dativ:2",
        "passiv-modalverb:1", "passiv-modalverb:2", "passiv-modalverb:3",
    ]
    assert all("answer" not in item and "explanation" not in item for item in exercises)
    assert exercises[2]["options"] == ["der", "die", "den"]
    assert shown["results"] == {
        "dativ:1": {
            "answer": "den",
            "right": False,
            "correction": "Ich helfe dem Kind.",
            "reason": "helfen takes the dative.",
        }
    }
    assert shown["finished"] is False
    assert lessons.read(1) == LESSON
