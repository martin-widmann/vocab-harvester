"""Curriculum and Topic state: the ordered map of Grammar topics, and how far
the learner is with each one.

An agent drafts the Curriculum and can propose changes. A proposal is only
stored as the Curriculum when the learner approves it, on the command line:
no MCP tool can approve.
"""

import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path


@dataclass(frozen=True)
class Topic:
    """One Grammar topic: a short id, the name a Tag shows, and its CEFR level."""

    id: str
    name: str
    level: str


class TopicState(Enum):
    NOT_SEEN = "Not seen"
    SEEN = "Seen"
    LEARNED = "Learned"
    SOLID = "Solid"


@dataclass(frozen=True)
class TopicStatus:
    """A Grammar topic of the Curriculum and the learner's Topic state of it."""

    topic: Topic
    state: TopicState
    weak: bool = False  # A Weak point: a review failed since it was last Solid.


@dataclass(frozen=True)
class Proposal:
    """A full Curriculum that waits for the learner's approval.

    `added` and `removed` name the topic ids it adds to and removes from the
    current Curriculum, in their order.
    """

    number: int
    topics: list[Topic]
    added: list[str]
    removed: list[str]


@dataclass(frozen=True)
class LessonTopics:
    """The 2 Grammar topics a Lesson can teach, from the topics found in its Episode.

    `new` is the next new topic, `weak` a Weak point; either is None when the
    Episode has none. `not_in_curriculum` names found topics the Curriculum
    does not have.
    """

    new: Topic | None
    weak: Topic | None
    not_in_curriculum: list[str]


REVIEWS_TO_SOLID = 3
LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
# The learner is B2, so the topics up to B1 start as Solid.
SOLID_LEVELS = ("A1", "A2", "B1")
_TOPIC_ID = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


def _start_state(topic: Topic) -> TopicState:
    return TopicState.SOLID if topic.level in SOLID_LEVELS else TopicState.NOT_SEEN


def check_topic_id(topic_id: str) -> None:
    """Reject a topic id that is not lowercase letters and digits with hyphens."""
    if not _TOPIC_ID.fullmatch(topic_id):
        raise ValueError(
            f"Topic id {topic_id!r} must be lowercase letters and digits "
            'with single hyphens, for example "konjunktiv-2"'
        )


def _reject_malformed(topics: list[Topic]) -> None:
    """Reject a malformed Curriculum before it is kept."""
    if not topics:
        raise ValueError("A Curriculum needs Grammar topics; this one has no Grammar topics")
    seen: set[str] = set()
    for topic in topics:
        check_topic_id(topic.id)
        if topic.id in seen:
            raise ValueError(f"Topic id {topic.id!r} is in the proposal twice")
        seen.add(topic.id)
        if not topic.name.strip():
            raise ValueError(f"Topic {topic.id!r} needs a name")
        if topic.level not in LEVELS:
            raise ValueError(
                f"Topic {topic.id!r} has level {topic.level!r}; the level must be one of "
                + ", ".join(LEVELS)
            )


_STATES = ", ".join(f"'{state.value}'" for state in TopicState)

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS curriculum_topics (
    topic_id TEXT PRIMARY KEY,
    position INTEGER NOT NULL,
    name TEXT NOT NULL,
    level TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ({_STATES})),
    passed_in_a_row INTEGER NOT NULL DEFAULT 0,
    -- For a Weak point: when it became weak, as a count. NULL when not weak.
    weak_since INTEGER
);
CREATE TABLE IF NOT EXISTS curriculum_proposal (
    -- AUTOINCREMENT: a new proposal never takes the number of an old one.
    number INTEGER PRIMARY KEY AUTOINCREMENT,
    topics TEXT NOT NULL
);
"""


class Curriculum:
    """The learner's Curriculum and Topic states, in the vocab SQLite file."""

    def __init__(self, path: Path | str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.executescript(_SCHEMA)

    def close(self) -> None:
        self._db.close()

    def propose(self, topics: list[Topic]) -> Proposal:
        """Keep a full Curriculum as the proposal; it replaces an older proposal."""
        _reject_malformed(topics)
        with self._db:
            self._db.execute("DELETE FROM curriculum_proposal")
            self._db.execute(
                "INSERT INTO curriculum_proposal (topics) VALUES (?)",
                (json.dumps([asdict(topic) for topic in topics], ensure_ascii=False),),
            )
        return self.proposal()

    def proposal(self) -> Proposal | None:
        row = self._db.execute(
            "SELECT number, topics FROM curriculum_proposal"
        ).fetchone()
        if row is None:
            return None
        number, stored = row
        topics = [Topic(**topic) for topic in json.loads(stored)]
        proposed = [topic.id for topic in topics]
        current = [status.topic.id for status in self.topics()]
        return Proposal(
            number,
            topics,
            added=[topic_id for topic_id in proposed if topic_id not in current],
            removed=[topic_id for topic_id in current if topic_id not in proposed],
        )

    def approve(self, number: int) -> list[TopicStatus]:
        """Store the proposal with this number as the Curriculum.

        A topic it keeps keeps its Topic state, also when its name or level
        changed; only a Not seen topic moved to B1 or lower starts as Solid,
        like a new one. A topic it adds starts as Solid up to B1, else as Not
        seen. A topic it removes loses its Topic state.
        """
        proposal = self.proposal()
        if proposal is None:
            raise ValueError("No open proposal: propose the Curriculum first")
        if proposal.number != number:
            raise ValueError(
                f"Proposal {number} is not the open proposal; "
                f"the open proposal is {proposal.number}"
            )
        with self._db:
            for topic_id in proposal.removed:
                self._db.execute(
                    "DELETE FROM curriculum_topics WHERE topic_id = ?", (topic_id,)
                )
            for position, topic in enumerate(proposal.topics):
                self._db.execute(
                    "INSERT INTO curriculum_topics "
                    "(topic_id, position, name, level, state) VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT (topic_id) DO UPDATE SET position = excluded.position, "
                    "name = excluded.name, level = excluded.level, "
                    "state = CASE WHEN state = ? THEN excluded.state ELSE state END",
                    (
                        topic.id,
                        position,
                        topic.name,
                        topic.level,
                        _start_state(topic).value,
                        TopicState.NOT_SEEN.value,
                    ),
                )
            self._db.execute("DELETE FROM curriculum_proposal")
        return self.topics()

    def topics(self) -> list[TopicStatus]:
        """Each topic of the Curriculum with its Topic state, in Curriculum order."""
        rows = self._db.execute(
            "SELECT topic_id, name, level, state, weak_since IS NOT NULL "
            "FROM curriculum_topics ORDER BY position"
        )
        return [
            TopicStatus(Topic(topic_id, name, level), TopicState(state), bool(weak))
            for topic_id, name, level, state, weak in rows
        ]

    def weak_points(self) -> list[Topic]:
        """The Weak points, the one that has been weak the longest first."""
        rows = self._db.execute(
            "SELECT topic_id, name, level FROM curriculum_topics "
            "WHERE weak_since IS NOT NULL ORDER BY weak_since"
        )
        return [Topic(*row) for row in rows]

    def taught(self, topic_id: str) -> None:
        """A Lesson taught the topic: Not seen becomes Seen."""
        self._move(topic_id, TopicState.NOT_SEEN, TopicState.SEEN)

    def lesson_exercises_passed(self, topic_id: str) -> None:
        """The learner passed the topic's Lesson exercises: Seen becomes Learned.

        A Learned or Solid topic (a Weak point a Lesson taught again) stays.
        """
        if self._state_of(topic_id) == TopicState.NOT_SEEN:
            raise ValueError(f"{topic_id!r} is Not seen: no Lesson taught it")
        self._move(topic_id, TopicState.SEEN, TopicState.LEARNED)

    def review(self, topic_id: str, passed: bool) -> None:
        """A grammar review of a Learned or Solid topic.

        3 reviews passed in a row make it Solid, and it stops being a Weak
        point. A failed review sets it back to Learned as a Weak point.
        """
        state = self._state_of(topic_id)
        if state not in (TopicState.LEARNED, TopicState.SOLID):
            raise ValueError(
                f"{topic_id!r} is {state.value}, not Learned or Solid: it has no reviews yet"
            )
        with self._db:
            if passed:
                self._db.execute(
                    "UPDATE curriculum_topics SET passed_in_a_row = passed_in_a_row + 1 "
                    "WHERE topic_id = ?",
                    (topic_id,),
                )
                self._db.execute(
                    "UPDATE curriculum_topics SET state = ?, weak_since = NULL "
                    "WHERE topic_id = ? AND passed_in_a_row >= ?",
                    (TopicState.SOLID.value, topic_id, REVIEWS_TO_SOLID),
                )
            else:
                self._db.execute(
                    "UPDATE curriculum_topics SET state = ?, passed_in_a_row = 0, "
                    "weak_since = COALESCE(weak_since, "
                    "(SELECT COALESCE(MAX(weak_since), 0) + 1 FROM curriculum_topics)) "
                    "WHERE topic_id = ?",
                    (TopicState.LEARNED.value, topic_id),
                )

    def _move(self, topic_id: str, before: TopicState, after: TopicState) -> None:
        """Set the topic to `after` if it is `before`; a topic further on stays."""
        self._state_of(topic_id)  # Only to reject a topic not in the Curriculum.
        with self._db:
            self._db.execute(
                "UPDATE curriculum_topics SET state = ? WHERE topic_id = ? AND state = ?",
                (after.value, topic_id, before.value),
            )

    def _state_of(self, topic_id: str) -> TopicState:
        row = self._db.execute(
            "SELECT state FROM curriculum_topics WHERE topic_id = ?", (topic_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Grammar topic {topic_id!r} is not in the Curriculum")
        return TopicState(row[0])


def curriculum_gaps(curriculum: Curriculum, found: list[str]) -> LessonTopics:
    """Pick the Grammar topics for a Lesson from the topics found in its Episode.

    The new topic is the first Not seen topic in Curriculum order. The weak
    topic is the Weak point that has been weak the longest. Both come only
    from `found`, so a Lesson teaches only topics of its own Episode.
    """
    topics = curriculum.topics()
    if not topics:
        raise ValueError(
            "No Curriculum yet: draft one and store it after the learner approves it"
        )
    in_curriculum = {status.topic.id for status in topics}
    found_ids = set(found)
    new = next(
        (
            status.topic
            for status in topics
            if status.state == TopicState.NOT_SEEN and status.topic.id in found_ids
        ),
        None,
    )
    weak = next(
        (topic for topic in curriculum.weak_points() if topic.id in found_ids), None
    )
    not_in_curriculum = [
        topic_id for topic_id in dict.fromkeys(found) if topic_id not in in_curriculum
    ]
    return LessonTopics(new, weak, not_in_curriculum)
