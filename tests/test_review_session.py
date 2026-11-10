"""Finish a review session: what the day's reviews did, and the learner summary."""

from datetime import date, datetime, timedelta, timezone

import pytest
from fakes import FakeClock, FakeDateClock, FakeLanguageTool

from core import (
    Curriculum,
    Exercise,
    ExerciseStock,
    FoundTopic,
    LearnerSummary,
    LessonFiles,
    Line,
    ReviewDay,
    SentenceChecker,
    Teaching,
    Topic,
    VocabStore,
    WordState,
    add_exercises,
    answer_grammar,
    due_grammar,
    finish_review,
    grade_card,
    report_topics,
)

START = datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc)
YESTERDAY = date(2026, 11, 9)


@pytest.fixture
def db(tmp_path):
    return tmp_path / "vocab.sqlite"


@pytest.fixture
def store(db):
    store = VocabStore(db)
    yield store
    store.close()


@pytest.fixture
def curriculum(db):
    curriculum = Curriculum(db)
    curriculum.approve(curriculum.propose([
        Topic("dativ", "Dativ", "B2"), Topic("konjunktiv-1", "Konjunktiv I", "B2"),
    ]).number)
    yield curriculum
    curriculum.close()


@pytest.fixture
def stock(db):
    stock = ExerciseStock(db)
    yield stock
    stock.close()


@pytest.fixture
def summary(db):
    return LearnerSummary.next_to(db)


@pytest.fixture
def clock():
    return FakeDateClock(START)


def taught(store, base_form, word_type="VERB", gender=None):
    store.add(base_form, word_type, WordState.UNKNOWN)
    store.add_example_sentence(base_form, 1, f"Ein Satz mit {base_form}.")
    store.teach(base_form, Teaching("Test/S01E01", YESTERDAY, base_form, "a meaning", gender))


def learned(curriculum, stock, topic_id):
    """A Learned topic with a stock of 2 exercises."""
    lines = [Line(1, timedelta(seconds=1), timedelta(seconds=2), "Ich helfe dem Mann.")]
    report_topics(curriculum, stock, f"Build/{topic_id}", lines, [FoundTopic(topic_id, [1])])
    add_exercises(
        curriculum,
        stock,
        SentenceChecker(FakeLanguageTool(), FakeClock()),
        [
            Exercise(topic_id, "gap", f"Satz {n} mit ___.", f"lösung{n}", [], "Grund.")
            for n in (1, 2)
        ],
    )
    curriculum.taught(topic_id)
    curriculum.lesson_exercises_passed(topic_id)


def finish(db, store, curriculum, stock, summary, clock):
    return finish_review(
        store=store,
        curriculum=curriculum,
        stock=stock,
        lessons=LessonFiles.next_to(db),
        summary=summary,
        clock=clock,
    )


def test_finish_gives_what_the_reviews_of_the_day_did_and_what_is_still_due(
    db, store, curriculum, stock, summary, clock
):
    taught(store, "aufgeben")
    taught(store, "Höhle", "NOUN", gender="feminine")
    taught(store, "suchen")
    learned(curriculum, stock, "dativ")
    learned(curriculum, stock, "konjunktiv-1")
    grade_card(store, "aufgeben", "Again", clock)
    grade_card(store, "Höhle", "Good", clock, article="der")
    dativ, konjunktiv = due_grammar(curriculum, stock, clock)
    answer_grammar(curriculum, stock, dativ.exercise_id, "lösung1", clock)
    answer_grammar(curriculum, stock, konjunktiv.exercise_id, "falsch", clock)

    day = finish(db, store, curriculum, stock, summary, clock)

    assert day == ReviewDay(
        vocab_reviews=2,
        vocab_again=1,
        wrong_articles=1,
        grammar_reviews=2,
        grammar_right=1,
        vocab_due=1,  # suchen; aufgeben comes back some minutes after Again
        grammar_due=0,
    )


def test_finish_makes_the_learner_summary_again(
    db, store, curriculum, stock, summary, clock
):
    taught(store, "aufgeben")
    learned(curriculum, stock, "konjunktiv-1")
    grade_card(store, "aufgeben", "Again", clock)
    (card,) = due_grammar(curriculum, stock, clock)
    answer_grammar(curriculum, stock, card.exercise_id, "falsch", clock)

    finish(db, store, curriculum, stock, summary, clock)

    text = summary.read()
    assert "Rated Again in the last 7 days: aufgeben (1)" in text
    assert "Weak points: Konjunktiv I (konjunktiv-1)" in text
    assert "Made on 2026-11-10" in text


def test_finish_with_no_reviews_today_still_makes_the_summary(
    db, store, curriculum, stock, summary, clock
):
    day = finish(db, store, curriculum, stock, summary, clock)

    assert day == ReviewDay(0, 0, 0, 0, 0, 0, 0)
    assert summary.read() is not None
