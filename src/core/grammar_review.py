"""Grammar review: exercises from the stock, on the Review tab.

Each grammar review uses an exercise from the exercise stock that no review
used before. A script checks the answer, and the result moves the Topic
state: 3 reviews passed in a row make a topic Solid; a failed review sets it
back to Learned as a Weak point.

Which topics are due on a review day:
- A Learned topic, once a day. A Weak point comes first, the one weak the
  longest first; then the other Learned topics in Curriculum order.
- A Solid topic, once every 7 days, after the Learned topics.
- Only a topic with an unused exercise in its stock. A topic whose stock is
  used up waits for the refill at the next lesson build.
At most 5 grammar exercises a day; the rest move to the next day.
"""

import threading
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone

from core.curriculum import Curriculum, TopicState, TopicStatus
from core.grammar_topics import ExerciseStock, StoredExercise
from core.results import Result, check_fixed_answer
from core.review import Clock

DAILY_GRAMMAR_LIMIT = 5
SOLID_INTERVAL = timedelta(days=7)
# The web server answers in more than one thread: one answer at a time, so a
# double click cannot use an exercise twice.
_ANSWER_LOCK = threading.Lock()


@dataclass(frozen=True)
class GrammarCard:
    """A due grammar exercise as the Review tab shows it: no answer.

    `weak` is True for a Weak point.
    """

    exercise_id: int
    topic_id: str
    topic_name: str
    kind: str
    sentence: str
    options: list[str]
    weak: bool


@dataclass(frozen=True)
class GrammarGraded:
    """A saved grammar review: its result and the topic's Topic state now."""

    topic_id: str
    result: Result
    state: TopicState
    weak: bool


def due_grammar(
    curriculum: Curriculum, stock: ExerciseStock, clock: Clock
) -> list[GrammarCard]:
    """Today's due grammar exercises: one per due topic, at most 5 a day."""
    return [
        _card(status, stored)
        for status, stored in _due(curriculum, stock, _now(clock).date())
    ]


def answer_grammar(
    curriculum: Curriculum,
    stock: ExerciseStock,
    exercise_id: int,
    answer: str,
    clock: Clock,
) -> GrammarGraded:
    """Check the answer to a due grammar exercise; the result moves the Topic state.

    The exercise leaves the stock. An exercise that is not due today is
    rejected, and so is an answer the script cannot check (a choice that is
    not an option); neither changes anything.
    """
    with _ANSWER_LOCK:
        now = _now(clock)
        found = next(
            (
                (status, stored)
                for status, stored in _due(curriculum, stock, now.date())
                if stored.id == exercise_id
            ),
            None,
        )
        if found is None:
            raise ValueError(f"Grammar exercise {exercise_id} is not due today")
        status, stored = found
        result = check_fixed_answer(
            {"id": str(stored.id), **asdict(stored.exercise)}, answer
        )
        stock.record_review(
            stored.id,
            now.date(),
            now.astimezone(timezone.utc).isoformat(),
            answer,
            result.right,
        )
        curriculum.review(status.topic.id, passed=result.right)
        after = next(
            item for item in curriculum.topics() if item.topic.id == status.topic.id
        )
    return GrammarGraded(status.topic.id, result, after.state, after.weak)


def _now(clock: Clock) -> datetime:
    now = clock.now()
    if now.tzinfo is None:
        raise ValueError("The review clock must give the time with its time zone")
    return now


def _due(
    curriculum: Curriculum, stock: ExerciseStock, today: date
) -> list[tuple[TopicStatus, StoredExercise]]:
    done_today = stock.reviewed_on(today)
    room = DAILY_GRAMMAR_LIMIT - len(done_today)
    if room <= 0:
        return []
    statuses = curriculum.topics()
    weak_order = {topic.id: n for n, topic in enumerate(curriculum.weak_points())}
    learned = [status for status in statuses if status.state == TopicState.LEARNED]
    learned.sort(key=lambda status: weak_order.get(status.topic.id, len(weak_order)))
    solid = [
        status
        for status in statuses
        if status.state == TopicState.SOLID and _solid_due(stock, status, today)
    ]
    due = []
    for status in learned + solid:
        if status.topic.id in done_today:
            continue
        unused = stock.unused(status.topic.id)
        if unused:
            due.append((status, unused[0]))
    return due[:room]


def _solid_due(stock: ExerciseStock, status: TopicStatus, today: date) -> bool:
    last = stock.last_reviewed(status.topic.id)
    return last is None or today - last >= SOLID_INTERVAL


def _card(status: TopicStatus, stored: StoredExercise) -> GrammarCard:
    return GrammarCard(
        stored.id,
        status.topic.id,
        status.topic.name,
        stored.exercise.kind,
        stored.exercise.sentence,
        stored.exercise.options,
        status.weak,
    )
