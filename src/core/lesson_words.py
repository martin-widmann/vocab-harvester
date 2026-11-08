"""Lesson word picker: the Unknown words of an Episode that its Lesson teaches."""

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from core.episode import subtitle_file
from core.frequency import FrequencyTable
from core.subtitles import Line, read_lines
from core.vocab_store import VocabStore, WordState
from core.word_analysis import analyse_all

LESSON_WORD_LIMIT = 20
SECTION_LENGTH = timedelta(minutes=15)
SECTION_COUNT = 3


@dataclass(frozen=True)
class LessonWord:
    """An Unknown word picked for a Lesson, with where it is first heard."""

    base_form: str
    word_type: str
    count: int | None
    section: int
    line: Line
    seen_form: str


def pick_lesson_words(
    episode_folder: Path | str,
    store: VocabStore,
    frequency: FrequencyTable,
) -> list[LessonWord]:
    """Pick up to 20 Unknown words of an Episode, the most frequent first.

    Base forms the frequency table does not have come last. Words with the same
    count keep the order they are first heard in. Each word goes to the
    Section of the first Line it is heard in: 1, 2 or 3 for about 0-15,
    15-30 and 30-45 minutes; a Line after 45 minutes is in Section 3.

    Picking changes no word state: the words not picked stay Unknown.
    """
    lines = read_lines(subtitle_file(episode_folder))
    found: dict[str, LessonWord] = {}
    for line, words in zip(lines, analyse_all(line.text for line in lines)):
        for word in words:
            if word.base_form in found:
                continue
            if store.state_of(word.base_form) != WordState.UNKNOWN:
                continue
            found[word.base_form] = LessonWord(
                word.base_form,
                word.word_type,
                frequency.count(word.base_form),
                _section(line),
                line,
                word.seen_form,
            )
    ranked = sorted(
        found.values(),
        key=lambda word: (word.count is None, -(word.count or 0)),
    )
    return ranked[:LESSON_WORD_LIMIT]


def _section(line: Line) -> int:
    return min(int(line.start // SECTION_LENGTH) + 1, SECTION_COUNT)
