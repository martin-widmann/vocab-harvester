"""Grammar topics of an Episode, and the exercise stock.

The topic-finder agent finds Grammar topics in an Episode's Lines and reports
them here. The core picks the 2 topics its Lesson teaches: 1 new topic and 1
Weak point. Each lesson build also says which topics need exercises: the 2
picked topics, and every topic whose stock ran low. The topic-finder writes
the exercises; LanguageTool checks each one before it goes into the stock.
"""

import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from core.curriculum import Curriculum, Topic, check_topic_id, curriculum_gaps
from core.sentences import MAX_RETRIES, SentenceChecker
from core.subtitles import Line

EXERCISES_PER_TOPIC = 5
GAP = "___"
MAX_TEXT_LENGTH = 300
MIN_OPTIONS = 2
MAX_OPTIONS = 4
# Like an example sentence: 1 try and 3 retries for each exercise a topic needs.
TRIES_PER_EXERCISE = MAX_RETRIES + 1


@dataclass(frozen=True)
class FoundTopic:
    """A Grammar topic the topic-finder found, with the numbers of its Lines."""

    topic_id: str
    lines: list[int]


@dataclass(frozen=True)
class PickedTopic:
    """A Grammar topic a Lesson teaches, with the Lines of the Episode it is in."""

    topic: Topic
    lines: list[int]


@dataclass(frozen=True)
class Refill:
    """A topic whose stock this lesson build fills up: `needed` more exercises."""

    topic: Topic
    in_stock: int
    needed: int


@dataclass(frozen=True)
class LessonGrammar:
    """The Grammar topics of a Lesson, and the topics whose stock needs exercises.

    `new` is the next new topic and `weak` a Weak point; either is None when
    the Episode has none. `not_in_curriculum` names found topics the
    Curriculum does not have.
    """

    new: PickedTopic | None
    weak: PickedTopic | None
    not_in_curriculum: list[str]
    refill: list[Refill]


class ExerciseKind(str, Enum):
    GAP = "gap"  # Fill the gap; a script compares the answer.
    CHOICE = "choice"  # Pick one of the options for the gap.


@dataclass(frozen=True)
class Exercise:
    """A grammar exercise: a German sentence with one gap "___" and its answer.

    A "choice" exercise has 2 to 4 options, the answer one of them; a "gap"
    exercise has none. The explanation is the short reason a result shows.
    """

    topic_id: str
    kind: str
    sentence: str
    answer: str
    options: list[str]
    explanation: str

    @property
    def solved(self) -> str:
        """The sentence with the answer in the gap."""
        return self.sentence.replace(GAP, self.answer)


@dataclass(frozen=True)
class StoredExercise:
    id: int
    exercise: Exercise


class ExerciseStatus(str, Enum):
    STORED = "stored"
    RETRY = "retry"  # It failed; the agent writes a new exercise for the topic.
    STOPPED = "stopped"  # It failed and the topic has no tries left in this build.


@dataclass(frozen=True)
class ExerciseResult:
    topic_id: str
    sentence: str
    status: ExerciseStatus
    problems: list[str]
    retries_left: int | None  # None for a stored exercise


_SCHEMA = """
CREATE TABLE IF NOT EXISTS episode_topics (
    episode TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    lines TEXT NOT NULL,
    PRIMARY KEY (episode, topic_id)
);
CREATE TABLE IF NOT EXISTS exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    sentence TEXT NOT NULL,
    answer TEXT NOT NULL,
    options TEXT NOT NULL,
    explanation TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0
);
-- The topics a Lesson picked at least once: their stock is refilled when low.
CREATE TABLE IF NOT EXISTS stock_topics (
    topic_id TEXT PRIMARY KEY
);
-- The topics the latest lesson build fills up, and their failed tries left.
CREATE TABLE IF NOT EXISTS open_refills (
    topic_id TEXT PRIMARY KEY,
    episode TEXT NOT NULL,
    failures_left INTEGER NOT NULL
);
"""


class ExerciseStock:
    """The Grammar topics found per Episode and the exercise stock, in the vocab file."""

    def __init__(self, path: Path | str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.executescript(_SCHEMA)

    def close(self) -> None:
        self._db.close()

    def found_topics(self, episode: str) -> list[FoundTopic]:
        """The topics the last report for an Episode found, in report order."""
        rows = self._db.execute(
            "SELECT topic_id, lines FROM episode_topics WHERE episode = ? "
            "ORDER BY rowid",
            (episode,),
        )
        return [FoundTopic(topic_id, json.loads(lines)) for topic_id, lines in rows]

    def unused(self, topic_id: str) -> list[StoredExercise]:
        """The exercises of a topic no review has used yet, oldest first."""
        rows = self._db.execute(
            "SELECT id, topic_id, kind, sentence, answer, options, explanation "
            "FROM exercises WHERE topic_id = ? AND NOT used ORDER BY id",
            (topic_id,),
        )
        return [
            StoredExercise(
                id, Exercise(topic, kind, sentence, answer, json.loads(options), why)
            )
            for id, topic, kind, sentence, answer, options, why in rows
        ]

    def mark_used(self, exercise_id: int) -> None:
        """A review used the exercise: it leaves the stock."""
        with self._db:
            changed = self._db.execute(
                "UPDATE exercises SET used = 1 WHERE id = ? AND NOT used",
                (exercise_id,),
            ).rowcount
        if not changed:
            raise ValueError(f"Exercise {exercise_id} is not in the stock")

    def _keep_found(self, episode: str, found: list[FoundTopic]) -> None:
        self._db.execute("DELETE FROM episode_topics WHERE episode = ?", (episode,))
        self._db.executemany(
            "INSERT INTO episode_topics (episode, topic_id, lines) VALUES (?, ?, ?)",
            [(episode, item.topic_id, json.dumps(item.lines)) for item in found],
        )

    def _start_build(
        self, episode: str, picks: list[Topic], refills: list[Refill]
    ) -> None:
        """A lesson build: only its refills are open.

        Each starts with fresh tries; a new report for the same Episode keeps
        the tries left of the topics its last report opened.
        """
        kept = dict(
            self._db.execute(
                "SELECT topic_id, failures_left FROM open_refills WHERE episode = ?",
                (episode,),
            ).fetchall()
        )
        self._db.executemany(
            "INSERT OR IGNORE INTO stock_topics (topic_id) VALUES (?)",
            [(topic.id,) for topic in picks],
        )
        self._db.execute("DELETE FROM open_refills")
        self._db.executemany(
            "INSERT INTO open_refills (topic_id, episode, failures_left) "
            "VALUES (?, ?, ?)",
            [
                (
                    refill.topic.id,
                    episode,
                    kept.get(refill.topic.id, TRIES_PER_EXERCISE * refill.needed),
                )
                for refill in refills
            ],
        )

    def _failures_left(self, topic_id: str) -> int | None:
        """The failed tries left for an open refill, or None if it is not open."""
        row = self._db.execute(
            "SELECT failures_left FROM open_refills WHERE topic_id = ?", (topic_id,)
        ).fetchone()
        return row and row[0]

    def _stocked_topics(self) -> set[str]:
        """The topics a Lesson picked at least once."""
        return {row[0] for row in self._db.execute("SELECT topic_id FROM stock_topics")}

    def _solved_sentences(self, topic_id: str) -> set[str]:
        rows = self._db.execute(
            "SELECT sentence, answer FROM exercises WHERE topic_id = ?", (topic_id,)
        )
        return {sentence.replace(GAP, answer) for sentence, answer in rows}

    def _store(self, exercise: Exercise) -> None:
        self._db.execute(
            "INSERT INTO exercises "
            "(topic_id, kind, sentence, answer, options, explanation) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                exercise.topic_id,
                exercise.kind,
                exercise.sentence,
                exercise.answer,
                json.dumps(exercise.options, ensure_ascii=False),
                exercise.explanation,
            ),
        )

    def _fail(self, topic_id: str) -> int:
        """Count a failed try for a topic; give its failed tries left."""
        self._db.execute(
            "UPDATE open_refills SET failures_left = MAX(failures_left - 1, 0) "
            "WHERE topic_id = ?",
            (topic_id,),
        )
        return self._failures_left(topic_id) or 0


def report_topics(
    curriculum: Curriculum,
    stock: ExerciseStock,
    episode: str,
    lines: list[Line],
    found: list[FoundTopic],
) -> LessonGrammar:
    """A lesson build: keep the topics found in an Episode and pick the 2 its Lesson teaches.

    A new report for the same Episode replaces the old one. The refill names
    the picked topics and every topic a Lesson picked before whose stock is
    low (fewer than 5 unused exercises), each with the number of exercises it
    needs. Only these topics take new exercises until the next lesson build.
    """
    found = _checked_report(lines, found)
    gaps = curriculum_gaps(curriculum, [item.topic_id for item in found])
    lines_of = {item.topic_id: item.lines for item in found}

    def picked(topic: Topic | None) -> PickedTopic | None:
        return topic and PickedTopic(topic, lines_of[topic.id])

    picks = [topic for topic in (gaps.new, gaps.weak) if topic]
    stocked = stock._stocked_topics()
    others = [
        status.topic
        for status in curriculum.topics()
        if status.topic.id in stocked and status.topic not in picks
    ]
    refill = []
    for topic in picks + others:
        in_stock = len(stock.unused(topic.id))
        if in_stock < EXERCISES_PER_TOPIC:
            refill.append(Refill(topic, in_stock, EXERCISES_PER_TOPIC - in_stock))
    with stock._db:
        stock._keep_found(episode, found)
        stock._start_build(episode, picks, refill)
    return LessonGrammar(
        picked(gaps.new), picked(gaps.weak), gaps.not_in_curriculum, refill
    )


def add_exercises(
    curriculum: Curriculum,
    stock: ExerciseStock,
    checker: SentenceChecker,
    exercises: list[Exercise],
) -> list[ExerciseResult]:
    """Check exercises with LanguageTool and store the ones that pass in the stock.

    LanguageTool checks each sentence with the answer in the gap. Only a topic
    of the latest lesson build's refill takes exercises, up to 5 unused in
    stock. A topic has 1 try and 3 retries for each exercise it needed at the
    build; when they all fail, it stops until the next lesson build.
    """
    exercises = _checked_exercises(curriculum, stock, exercises)
    results = []
    problems_of = checker.check([exercise.solved for exercise in exercises])
    with stock._db:
        for exercise, problems in zip(exercises, problems_of):
            if problems:
                left = stock._fail(exercise.topic_id)
                status = ExerciseStatus.RETRY if left else ExerciseStatus.STOPPED
                results.append(
                    ExerciseResult(
                        exercise.topic_id, exercise.sentence, status, problems, left
                    )
                )
            else:
                stock._store(exercise)
                results.append(
                    ExerciseResult(
                        exercise.topic_id,
                        exercise.sentence,
                        ExerciseStatus.STORED,
                        [],
                        None,
                    )
                )
    return results


def _checked_report(lines: list[Line], found: list[FoundTopic]) -> list[FoundTopic]:
    """The found topics with sorted Line numbers; ValueError if any one is bad."""
    numbers = {line.number for line in lines}
    seen: set[str] = set()
    checked = []
    for item in found:
        check_topic_id(item.topic_id)
        if item.topic_id in seen:
            raise ValueError(f"Topic {item.topic_id!r} is in the report twice")
        seen.add(item.topic_id)
        if not item.lines:
            raise ValueError(f"Topic {item.topic_id!r} needs the Lines it occurs in")
        for number in item.lines:
            if number not in numbers:
                raise ValueError(
                    f"Topic {item.topic_id!r}: the Episode has no Line {number}"
                )
        checked.append(FoundTopic(item.topic_id, sorted(set(item.lines))))
    return checked


def _checked_exercises(
    curriculum: Curriculum, stock: ExerciseStock, exercises: list[Exercise]
) -> list[Exercise]:
    """The exercises with outer spaces removed; ValueError if any one is bad."""
    names = {status.topic.id: status.topic.name for status in curriculum.topics()}
    per_topic: Counter[str] = Counter()
    seen: set[tuple[str, str]] = set()
    cleaned = []
    for exercise in exercises:
        exercise = _cleaned(exercise)
        topic_id = exercise.topic_id
        name = f"Exercise {exercise.sentence!r} of {topic_id!r}"
        if topic_id not in names:
            raise ValueError(f"Grammar topic {topic_id!r} is not in the Curriculum")
        failures_left = stock._failures_left(topic_id)
        if failures_left is None:
            raise ValueError(
                f"{topic_id!r} is not in the refill of the latest lesson build; "
                "only those topics take exercises"
            )
        if failures_left == 0:
            raise ValueError(
                f"{topic_id!r} failed all its tries; it takes exercises again "
                "at the next lesson build"
            )
        _check_exercise(name, exercise)
        key = (topic_id, exercise.solved)
        if key in seen or exercise.solved in stock._solved_sentences(topic_id):
            raise ValueError(f"{name} is already in the stock or in this call")
        seen.add(key)
        per_topic[topic_id] += 1
        cleaned.append(exercise)
    for topic_id, count in per_topic.items():
        room = EXERCISES_PER_TOPIC - len(stock.unused(topic_id))
        if count > room:
            raise ValueError(
                f"{topic_id!r} has room for {room} more exercises, not {count}; "
                f"the stock holds {EXERCISES_PER_TOPIC} per topic"
            )
    return cleaned


def _cleaned(exercise: Exercise) -> Exercise:
    return Exercise(
        exercise.topic_id,
        exercise.kind,
        exercise.sentence.strip(),
        exercise.answer.strip(),
        [option.strip() for option in exercise.options],
        exercise.explanation.strip(),
    )


def _check_exercise(name: str, exercise: Exercise) -> None:
    kinds = [kind.value for kind in ExerciseKind]
    if exercise.kind not in kinds:
        raise ValueError(f"{name}: the kind must be one of {', '.join(kinds)}")
    texts = {
        "sentence": exercise.sentence,
        "answer": exercise.answer,
        "explanation": exercise.explanation,
        **{f"option {n}": option for n, option in enumerate(exercise.options, 1)},
    }
    for field, text in texts.items():
        if not text:
            raise ValueError(f"{name}: the {field} is empty")
        if len(text) > MAX_TEXT_LENGTH:
            raise ValueError(
                f"{name}: the {field} is too long; use at most {MAX_TEXT_LENGTH} characters"
            )
        if len(text.splitlines()) > 1:
            raise ValueError(f"{name}: the {field} must be one line")
        if field != "sentence" and GAP in text:
            raise ValueError(f"{name}: only the sentence has the gap {GAP}")
    if exercise.sentence.count(GAP) != 1:
        raise ValueError(f"{name}: the sentence must have exactly one gap {GAP}")
    if exercise.kind == ExerciseKind.GAP and exercise.options:
        raise ValueError(f"{name}: a gap exercise has no options")
    if exercise.kind == ExerciseKind.CHOICE:
        if not MIN_OPTIONS <= len(exercise.options) <= MAX_OPTIONS:
            raise ValueError(
                f"{name}: a choice exercise has {MIN_OPTIONS} to {MAX_OPTIONS} options"
            )
        if len(set(exercise.options)) != len(exercise.options):
            raise ValueError(f"{name}: the options must be different")
        if exercise.answer not in exercise.options:
            raise ValueError(f"{name}: the answer must be one of the options")
