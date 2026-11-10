"""The learner summary: a short text of the learner state for the tutor."""

import json
from datetime import date

import pytest

from core import (
    Curriculum,
    LearnerSummary,
    LessonFiles,
    Topic,
    VocabStore,
    WordState,
)

TODAY = date(2026, 11, 10)


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
    yield curriculum
    curriculum.close()


@pytest.fixture
def lessons(db):
    return LessonFiles.next_to(db)


@pytest.fixture
def summary(db):
    return LearnerSummary.next_to(db)


def regenerate(summary, store, curriculum, lessons, today=TODAY) -> str:
    return summary.regenerate(
        store=store, curriculum=curriculum, lessons=lessons, today=today
    )


def test_there_is_no_summary_before_the_first_one_is_made(summary):
    assert summary.read() is None


def test_the_summary_counts_the_words_of_each_word_state(
    summary, store, curriculum, lessons
):
    for base_form in ["gehen", "Haus", "sehen"]:
        store.add(base_form, "VERB", WordState.KNOWN)
    store.add("aufgeben", "VERB", WordState.UNKNOWN)
    store.add("Höhle", "NOUN", WordState.TAUGHT)
    store.add("Martha", "PROPN", WordState.EXCLUDED)

    text = regenerate(summary, store, curriculum, lessons)

    assert "Known words: 3" in text
    assert "Unknown words: 1" in text
    assert "Taught words: 1" in text
    assert "Excluded words: 1" in text
    assert "2026-11-10" in text
    assert summary.read() == text


def test_a_new_summary_replaces_the_old_one(summary, store, curriculum, lessons):
    regenerate(summary, store, curriculum, lessons)
    store.add("gehen", "VERB", WordState.KNOWN)

    regenerate(summary, store, curriculum, lessons)

    assert "Known words: 1" in summary.read()


def approve(curriculum, topics):
    proposal = curriculum.propose(topics)
    curriculum.approve(proposal.number)


def test_the_summary_gives_the_topic_states_and_the_weak_points(
    summary, store, curriculum, lessons
):
    approve(curriculum, [
        Topic("perfekt", "Perfekt", "A2"),
        Topic("dativ", "Dativ", "B2"),
        Topic("konjunktiv-2", "Konjunktiv II", "B2"),
        Topic("passiv", "Passiv", "C1"),
    ])
    curriculum.taught("konjunktiv-2")
    curriculum.lesson_exercises_passed("konjunktiv-2")
    curriculum.review("konjunktiv-2", passed=False)
    curriculum.taught("dativ")

    text = regenerate(summary, store, curriculum, lessons)

    assert "Solid: 1" in text
    assert "Learned: 1" in text
    assert "Seen: 1" in text
    assert "Not seen: 1" in text
    assert "Weak points: Konjunktiv II (konjunktiv-2)" in text
    assert "Seen topics: Dativ (dativ)" in text


def test_the_summary_says_when_there_is_no_curriculum_yet(
    summary, store, curriculum, lessons
):
    text = regenerate(summary, store, curriculum, lessons)

    assert "No Curriculum yet" in text


def review(store, base_form, day, rating, article_right=None):
    store.save_review(base_form, "{}", f"{day.isoformat()}T08:00:00+00:00", day,
                      rating, article_right)


def test_the_summary_names_the_words_rated_again_in_the_last_7_days_most_first(
    summary, store, curriculum, lessons
):
    for base_form in ["aufgeben", "Höhle", "suchen", "warten"]:
        store.add(base_form, "NOUN", WordState.TAUGHT)
    review(store, "aufgeben", date(2026, 11, 9), "Again")
    review(store, "Höhle", date(2026, 11, 8), "Again")
    review(store, "Höhle", date(2026, 11, 9), "Again")
    review(store, "suchen", date(2026, 11, 9), "Good")
    review(store, "warten", date(2026, 11, 3), "Again")  # 7 days ago: too old

    text = regenerate(summary, store, curriculum, lessons)

    assert "Vocab reviews in the last 7 days: 4, Again: 3" in text
    assert "Rated Again in the last 7 days: Höhle (2), aufgeben (1)" in text
    assert "warten" not in text


def test_the_summary_names_the_nouns_with_a_wrong_article_in_the_last_7_days(
    summary, store, curriculum, lessons
):
    for base_form in ["Höhle", "Haus"]:
        store.add(base_form, "NOUN", WordState.TAUGHT)
    review(store, "Höhle", date(2026, 11, 9), "Good", article_right=False)
    review(store, "Haus", date(2026, 11, 9), "Good", article_right=True)

    text = regenerate(summary, store, curriculum, lessons)

    assert "Wrong article in the last 7 days: Höhle" in text


def test_the_summary_says_when_there_are_no_recent_mistakes(
    summary, store, curriculum, lessons
):
    text = regenerate(summary, store, curriculum, lessons)

    assert "Rated Again in the last 7 days: none" in text
    assert "Wrong article in the last 7 days: none" in text


def test_a_long_list_of_words_names_only_the_first_ones(
    summary, store, curriculum, lessons
):
    words = [f"Wort{n:02}" for n in range(20)]
    for base_form in words:
        store.add(base_form, "NOUN", WordState.TAUGHT)
        review(store, base_form, date(2026, 11, 9), "Again")

    text = regenerate(summary, store, curriculum, lessons)

    assert "Wort14 (1), and 5 more" in text
    assert "Wort15" not in text


def write_lesson_file(db, number, episode, finished=None):
    """A Lesson file in the lessons folder next to the vocab file, and its results."""
    folder = db.parent / "lessons"
    folder.mkdir(parents=True, exist_ok=True)
    lesson = {"schema_version": 1, "number": number, "episode": episode, "sections": []}
    (folder / f"lesson-{number:03}.json").write_text(json.dumps(lesson), encoding="utf-8")
    if finished is not None:
        results = {"schema_version": 1, "lesson": number, "episode": episode,
                   "answers": {}, "finished": finished}
        (folder / f"lesson-{number:03}.results.json").write_text(
            json.dumps(results), encoding="utf-8")


def test_the_summary_gives_the_lessons_and_the_ones_not_finished(
    db, summary, store, curriculum, lessons
):
    write_lesson_file(db, 1, "Dark/S01E01", finished=True)
    write_lesson_file(db, 2, "Dark/S01E02")
    write_lesson_file(db, 3, "Der Film/P1", finished=True)

    text = regenerate(summary, store, curriculum, lessons)

    assert "Lessons: 3, finished: 2" in text
    assert "Last Lesson: Lesson 3, Der Film/P1, finished" in text
    assert "Not finished: Lesson 2 (Dark/S01E02)" in text


def test_the_summary_says_when_there_is_no_lesson_yet(
    summary, store, curriculum, lessons
):
    text = regenerate(summary, store, curriculum, lessons)

    assert "No Lesson yet" in text
