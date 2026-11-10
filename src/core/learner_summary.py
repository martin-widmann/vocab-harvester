"""Learner summary: a short text of the learner state, for the tutor.

The tutor reads it at the start of each session, not the full history, so
its context stays small. A script makes it again at each Finish (of a
Lesson or of a review session). It is one Markdown file next to the vocab
file.
"""

import os
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from core.curriculum import Curriculum, TopicState
from core.lesson import LessonFiles
from core.vocab_store import VocabStore, WordState

FILE_NAME = "learner-summary.md"
# The recent mistakes come from the review days of the last week, today included.
RECENT_DAYS = 7
# A list of words or topics names at most this many, so the summary stays short.
MAX_NAMED = 15


class LearnerSummary:
    """The learner summary file."""

    def __init__(self, path: Path | str):
        self._path = Path(path)

    @classmethod
    def next_to(cls, db_path: Path | str) -> "LearnerSummary":
        """The learner summary of a learner: the file next to the vocab file."""
        return cls(Path(db_path).parent / FILE_NAME)

    @property
    def path(self) -> Path:
        return self._path

    def read(self) -> str | None:
        """The text of the latest summary; None before the first one is made."""
        try:
            return self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None

    def regenerate(
        self,
        *,
        store: VocabStore,
        curriculum: Curriculum,
        lessons: LessonFiles,
        today: date,
    ) -> str:
        """Make the summary again from the learner state now, and save it."""
        text = "\n".join(
            [
                "# Learner summary",
                "",
                f"Made on {today.isoformat()}.",
                "",
                *_vocab(store, today),
                "",
                *_grammar(curriculum),
                "",
                *_lessons(lessons),
                "",
            ]
        )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_name(self._path.name + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, self._path)
        return text


def _vocab(store: VocabStore, today: date) -> list[str]:
    counts = store.count_by_state()
    recent = store.review_log(today - timedelta(days=RECENT_DAYS - 1))
    again = Counter(review.base_form for review in recent if review.rating == "Again")
    wrong_article = list(
        dict.fromkeys(
            review.base_form for review in recent if review.article_right is False
        )
    )
    return [
        "## Vocab",
        "",
        *(
            f"- {state.value} words: {counts.get(state, 0)}"
            for state in WordState
        ),
        f"- Vocab reviews in the last {RECENT_DAYS} days: {len(recent)}, "
        f"Again: {sum(again.values())}",
        f"- Rated Again in the last {RECENT_DAYS} days: "
        + _listed([f"{word} ({count})" for word, count in again.most_common()]),
        f"- Wrong article in the last {RECENT_DAYS} days: " + _listed(wrong_article),
    ]


def _grammar(curriculum: Curriculum) -> list[str]:
    statuses = curriculum.topics()
    if not statuses:
        return ["## Grammar", "", "- No Curriculum yet."]
    lines = [
        "## Grammar",
        "",
        "- Topic states: "
        + ", ".join(
            f"{state.value}: {sum(1 for status in statuses if status.state == state)}"
            for state in TopicState
        ),
        f"- Weak points: {_names(curriculum.weak_points())}",
    ]
    for state, label in ((TopicState.LEARNED, "Learned"), (TopicState.SEEN, "Seen")):
        topics = [status.topic for status in statuses if status.state == state]
        lines.append(f"- {label} topics: {_names(topics)}")
    return lines


def _lessons(lessons: LessonFiles) -> list[str]:
    found = lessons.lessons()  # The newest first.
    if not found:
        return ["## Lessons", "", "- No Lesson yet."]
    finished = {info.number: _finished(lessons, info.number) for info in found}
    last = found[0]
    not_finished = [
        f"Lesson {info.number} ({info.episode})"
        for info in reversed(found)
        if finished[info.number] is False
    ]
    return [
        "## Lessons",
        "",
        f"- Lessons: {len(found)}, finished: {sum(1 for done in finished.values() if done)}",
        f"- Last Lesson: Lesson {last.number}, {last.episode}, "
        + {True: "finished", False: "not finished", None: "results cannot be read"}[
            finished[last.number]
        ],
        f"- Not finished: {_listed(not_finished)}",
    ]


def _finished(lessons: LessonFiles, number: int) -> bool | None:
    """Whether a Lesson is finished; None if its results file cannot be read."""
    try:
        return lessons.results(number)["finished"]
    except ValueError:
        return None


def _names(topics) -> str:
    return _listed([f"{topic.name} ({topic.id})" for topic in topics])


def _listed(items: list[str]) -> str:
    """The items as a list for the summary: at most MAX_NAMED, or "none"."""
    if not items:
        return "none"
    text = ", ".join(items[:MAX_NAMED])
    if len(items) > MAX_NAMED:
        text += f", and {len(items) - MAX_NAMED} more"
    return text
