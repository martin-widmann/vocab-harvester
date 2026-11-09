"""Grammar review: exercises from the stock move the Topic states."""

from datetime import date, datetime, timedelta, timezone

import pytest
from fakes import FakeClock, FakeDateClock, FakeLanguageTool

from core import (
    Curriculum,
    Exercise,
    ExerciseStock,
    FoundTopic,
    Line,
    SentenceChecker,
    Topic,
    TopicState,
    add_exercises,
    answer_grammar,
    due_grammar,
    report_topics,
)

START = datetime(2026, 11, 9, 8, 0, tzinfo=timezone.utc)

DRAFT = [
    Topic("dativ", "Dativ", "A2"),
    Topic("passiv-modalverb", "Passiv mit Modalverb", "B2"),
    Topic("konjunktiv-1", "Konjunktiv I", "B2"),
    Topic("konjunktiv-2", "Konjunktiv II", "B2"),
    Topic("futur-2", "Futur II", "C1"),
    Topic("partizip-1", "Partizip I", "C1"),
    Topic("genitiv-praep", "Präpositionen mit Genitiv", "B2"),
]


@pytest.fixture
def path(tmp_path):
    return tmp_path / "vocab.sqlite"


@pytest.fixture
def curriculum(path):
    curriculum = Curriculum(path)
    curriculum.approve(curriculum.propose(DRAFT).number)
    yield curriculum
    curriculum.close()


@pytest.fixture
def stock(path):
    stock = ExerciseStock(path)
    yield stock
    stock.close()


@pytest.fixture
def clock():
    return FakeDateClock(START)


def gap(topic_id, number):
    return Exercise(
        topic_id, "gap", f"Satz {number} mit ___.", f"lösung{number}", [], f"Grund {number}."
    )


LINES = [Line(1, timedelta(seconds=1), timedelta(seconds=2), "Er sagte, er sei müde.")]


def fill_stock(curriculum, stock, topic_id, numbers):
    """A lesson build picks the topic and the topic-finder stocks its exercises."""
    report_topics(curriculum, stock, f"Build/{topic_id}", LINES, [FoundTopic(topic_id, [1])])
    checker = SentenceChecker(FakeLanguageTool(), FakeClock())
    add_exercises(curriculum, stock, checker, [gap(topic_id, number) for number in numbers])


def learned(curriculum, stock, topic_id, exercises=5):
    """A topic a Lesson taught and whose Lesson exercises passed, with its stock."""
    fill_stock(curriculum, stock, topic_id, range(1, exercises + 1))
    curriculum.taught(topic_id)
    curriculum.lesson_exercises_passed(topic_id)


def state(curriculum, topic_id):
    return next(s for s in curriculum.topics() if s.topic.id == topic_id)


def test_a_learned_topic_is_due_with_an_exercise_from_its_stock(curriculum, stock, clock):
    learned(curriculum, stock, "konjunktiv-1")

    (card,) = due_grammar(curriculum, stock, clock)

    assert card.topic_id == "konjunktiv-1"
    assert card.topic_name == "Konjunktiv I"
    assert card.kind == "gap"
    assert card.sentence == "Satz 1 mit ___."
    assert card.options == []
    assert not hasattr(card, "answer")


def answer(curriculum, stock, clock, topic_id, right=True):
    """Answer today's due exercise of a topic, right or wrong."""
    card = next(c for c in due_grammar(curriculum, stock, clock) if c.topic_id == topic_id)
    number = card.sentence.split()[1]
    given = f"lösung{number}" if right else "falsch"
    return answer_grammar(curriculum, stock, card.exercise_id, given, clock)


def next_day(clock):
    clock.advance(days=1)


def test_a_script_checks_the_answer_and_gives_the_correction_and_reason(
    curriculum, stock, clock
):
    learned(curriculum, stock, "konjunktiv-1")
    (card,) = due_grammar(curriculum, stock, clock)

    graded = answer_grammar(curriculum, stock, card.exercise_id, "  LÖSUNG1 ", clock)

    assert graded.topic_id == "konjunktiv-1"
    assert graded.result.right is True
    assert graded.result.correction == "Satz 1 mit lösung1."
    assert graded.result.reason == "Grund 1."


def test_each_grammar_review_uses_an_exercise_not_used_before_for_the_topic(
    curriculum, stock, clock
):
    learned(curriculum, stock, "konjunktiv-1")

    sentences = []
    for _ in range(5):
        (card,) = due_grammar(curriculum, stock, clock)
        sentences.append(card.sentence)
        answer(curriculum, stock, clock, "konjunktiv-1", right=False)
        next_day(clock)

    assert sentences == [f"Satz {number} mit ___." for number in range(1, 6)]
    # The stock is used up: the topic waits for the refill at the next lesson build.
    assert due_grammar(curriculum, stock, clock) == []


def test_a_used_exercise_cannot_be_answered_again(curriculum, stock, clock):
    learned(curriculum, stock, "konjunktiv-1")
    (card,) = due_grammar(curriculum, stock, clock)
    answer_grammar(curriculum, stock, card.exercise_id, "lösung1", clock)
    next_day(clock)

    with pytest.raises(ValueError, match="not due"):
        answer_grammar(curriculum, stock, card.exercise_id, "lösung1", clock)
    assert state(curriculum, "konjunktiv-1").state == TopicState.LEARNED


def test_three_passed_reviews_in_a_row_make_a_topic_solid(curriculum, stock, clock):
    learned(curriculum, stock, "konjunktiv-1")

    states = []
    for _ in range(3):
        graded = answer(curriculum, stock, clock, "konjunktiv-1", right=True)
        states.append(graded.state)
        next_day(clock)

    assert states == [TopicState.LEARNED, TopicState.LEARNED, TopicState.SOLID]
    assert state(curriculum, "konjunktiv-1").state == TopicState.SOLID


def test_a_failed_review_breaks_the_row(curriculum, stock, clock):
    learned(curriculum, stock, "konjunktiv-1")

    for right in (True, True, False, True, True):
        answer(curriculum, stock, clock, "konjunktiv-1", right=right)
        next_day(clock)

    assert state(curriculum, "konjunktiv-1").state == TopicState.LEARNED


def test_a_failed_review_sets_the_topic_to_learned_and_makes_it_a_weak_point(
    curriculum, stock, clock
):
    learned(curriculum, stock, "konjunktiv-1", exercises=5)
    for _ in range(3):
        answer(curriculum, stock, clock, "konjunktiv-1", right=True)
        next_day(clock)
    assert state(curriculum, "konjunktiv-1").state == TopicState.SOLID
    clock.advance(days=7)

    graded = answer(curriculum, stock, clock, "konjunktiv-1", right=False)

    assert graded.result.right is False
    assert graded.result.correction == "Satz 4 mit lösung4."
    assert (graded.state, graded.weak) == (TopicState.LEARNED, True)
    assert curriculum.weak_points() == [Topic("konjunktiv-1", "Konjunktiv I", "B2")]


def test_a_weak_point_comes_first_in_the_reviews(curriculum, stock, clock):
    for topic_id in ("passiv-modalverb", "konjunktiv-1", "konjunktiv-2"):
        learned(curriculum, stock, topic_id)
    answer(curriculum, stock, clock, "konjunktiv-2", right=False)
    next_day(clock)

    cards = due_grammar(curriculum, stock, clock)

    assert [(card.topic_id, card.weak) for card in cards] == [
        ("konjunktiv-2", True),
        ("passiv-modalverb", False),
        ("konjunktiv-1", False),
    ]


def test_a_topic_gets_one_grammar_review_a_day(curriculum, stock, clock):
    learned(curriculum, stock, "konjunktiv-1")
    (card,) = due_grammar(curriculum, stock, clock)
    answer_grammar(curriculum, stock, card.exercise_id, "lösung1", clock)

    assert due_grammar(curriculum, stock, clock) == []
    next_day(clock)
    assert [card.sentence for card in due_grammar(curriculum, stock, clock)] == [
        "Satz 2 mit ___."
    ]


def test_a_solid_topic_comes_back_after_7_days(curriculum, stock, clock):
    learned(curriculum, stock, "konjunktiv-1")
    for _ in range(3):
        answer(curriculum, stock, clock, "konjunktiv-1", right=True)
        next_day(clock)
    last_review = clock.time - timedelta(days=1)

    clock.time = last_review + timedelta(days=6)
    assert due_grammar(curriculum, stock, clock) == []
    clock.time = last_review + timedelta(days=7)
    assert [card.topic_id for card in due_grammar(curriculum, stock, clock)] == [
        "konjunktiv-1"
    ]


def test_topics_with_no_lesson_get_no_grammar_reviews(curriculum, stock, clock):
    # Dativ (A2) starts Solid but has no stock; Futur II is Not seen; a Seen
    # topic has not passed its Lesson exercises yet.
    fill_stock(curriculum, stock, "futur-2", range(1, 6))
    fill_stock(curriculum, stock, "partizip-1", range(1, 6))
    curriculum.taught("partizip-1")

    assert due_grammar(curriculum, stock, clock) == []


TOPICS = ["passiv-modalverb", "konjunktiv-1", "konjunktiv-2", "futur-2", "partizip-1",
          "genitiv-praep"]


def test_at_most_5_grammar_exercises_a_day_the_rest_move_to_the_next_day(
    curriculum, stock, clock
):
    for topic_id in TOPICS:
        learned(curriculum, stock, topic_id)

    cards = due_grammar(curriculum, stock, clock)
    assert [card.topic_id for card in cards] == TOPICS[:5]
    for card in cards:
        answer(curriculum, stock, clock, card.topic_id)
    assert due_grammar(curriculum, stock, clock) == []

    next_day(clock)
    assert [card.topic_id for card in due_grammar(curriculum, stock, clock)] == TOPICS[:5]


def test_the_limit_counts_reviews_done_today(curriculum, stock, clock):
    for topic_id in TOPICS:
        learned(curriculum, stock, topic_id)
    for topic_id in TOPICS[:3]:
        answer(curriculum, stock, clock, topic_id)

    assert [card.topic_id for card in due_grammar(curriculum, stock, clock)] == TOPICS[3:5]


def test_the_review_day_is_the_date_of_the_learners_time_zone(curriculum, stock, clock):
    learned(curriculum, stock, "konjunktiv-1")
    berlin = timezone(timedelta(hours=1))
    clock.time = datetime(2026, 11, 9, 23, 30, tzinfo=berlin)
    answer(curriculum, stock, clock, "konjunktiv-1")

    clock.time = datetime(2026, 11, 10, 0, 10, tzinfo=berlin)  # Still 9 Nov in UTC.

    assert [card.topic_id for card in due_grammar(curriculum, stock, clock)] == [
        "konjunktiv-1"
    ]


def choice(topic_id):
    return Exercise(topic_id, "choice", "Er sagte, er ___ müde.", "sei",
                    ["sei", "ist", "wäre"], "Indirekte Rede: Konjunktiv I.")


def test_a_choice_that_is_not_an_option_is_rejected_and_changes_nothing(
    curriculum, stock, clock
):
    report_topics(curriculum, stock, "Build/x", LINES, [FoundTopic("konjunktiv-1", [1])])
    add_exercises(curriculum, stock, SentenceChecker(FakeLanguageTool(), FakeClock()),
                  [choice("konjunktiv-1")])
    curriculum.taught("konjunktiv-1")
    curriculum.lesson_exercises_passed("konjunktiv-1")
    (card,) = due_grammar(curriculum, stock, clock)
    assert (card.kind, card.options) == ("choice", ["sei", "ist", "wäre"])

    with pytest.raises(ValueError, match="Pick one of"):
        answer_grammar(curriculum, stock, card.exercise_id, "war", clock)

    assert due_grammar(curriculum, stock, clock) == [card]
    graded = answer_grammar(curriculum, stock, card.exercise_id, "ist", clock)
    assert graded.result.right is False
    assert graded.result.correction == "Er sagte, er sei müde."


def test_an_unknown_exercise_is_rejected(curriculum, stock, clock):
    learned(curriculum, stock, "konjunktiv-1")

    with pytest.raises(ValueError, match="not due"):
        answer_grammar(curriculum, stock, 999, "lösung1", clock)


def test_a_clock_with_no_time_zone_is_rejected(curriculum, stock, clock):
    learned(curriculum, stock, "konjunktiv-1")
    clock.time = datetime(2026, 11, 9, 8, 0)

    with pytest.raises(ValueError, match="time zone"):
        due_grammar(curriculum, stock, clock)
