"""Core of the German Media Learning system.

The names exported here are the public interface. The MCP server and the
web server are thin adapters over it.
"""

from core.curriculum import (
    Curriculum,
    Gaps,
    Proposal,
    Topic,
    TopicState,
    TopicStatus,
    curriculum_gaps,
)
from core.episode import NewWord, find_episode, new_words, subtitle_file
from core.frequency import FrequencyTable, build_frequency_table
from core.lesson_words import LessonWord, pick_lesson_words
from core.sentences import (
    Issue,
    LanguageToolBusy,
    SentenceChecker,
    SentenceResult,
    SentenceStatus,
    SentenceToStore,
    add_sentences,
    failed_sentences,
)
from core.subtitles import Line, SubtitleError, extract_subtitles, read_lines
from core.vocab_store import VocabStore, WordState
from core.word_analysis import Word, analyse
from core.word_check import CHECK_KEYS, record_answer
from core.word_facts import Facts, WordFacts, import_word_facts

__all__ = [
    "CHECK_KEYS",
    "Curriculum",
    "Facts",
    "Gaps",
    "FrequencyTable",
    "Issue",
    "LanguageToolBusy",
    "LessonWord",
    "Line",
    "NewWord",
    "Proposal",
    "SentenceChecker",
    "SentenceResult",
    "SentenceStatus",
    "SentenceToStore",
    "SubtitleError",
    "Topic",
    "TopicState",
    "TopicStatus",
    "VocabStore",
    "Word",
    "WordFacts",
    "WordState",
    "add_sentences",
    "analyse",
    "build_frequency_table",
    "curriculum_gaps",
    "extract_subtitles",
    "failed_sentences",
    "find_episode",
    "import_word_facts",
    "new_words",
    "pick_lesson_words",
    "read_lines",
    "record_answer",
    "subtitle_file",
]
