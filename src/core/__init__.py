"""Core of the German Media Learning system.

The names exported here are the public interface. The MCP server and the
web server are thin adapters over it.
"""

from core.curriculum import (
    Curriculum,
    LessonTopics,
    Proposal,
    Topic,
    TopicState,
    TopicStatus,
    curriculum_gaps,
)
from core.episode import NewWord, episode_key, find_episode, new_words, subtitle_file
from core.frequency import FrequencyTable, build_frequency_table
from core.grammar_topics import (
    Exercise,
    ExerciseKind,
    ExerciseResult,
    ExerciseStatus,
    ExerciseStock,
    FoundTopic,
    LessonGrammar,
    PickedTopic,
    Refill,
    StoredExercise,
    add_exercises,
    report_topics,
)
from core.grader import Grader, GraderError, GraderRunner
from core.lesson import (
    OPEN_KINDS,
    GrammarPart,
    LessonExercise,
    LessonFiles,
    LessonInfo,
    OpenKind,
    write_lesson,
)
from core.lesson_words import LessonWord, pick_lesson_words
from core.results import Finished, Result, TopicResult, check_answer, finish_lesson, lesson_for_page
from core.review import (
    DAILY_CARD_LIMIT,
    Graded,
    ReviewCard,
    SystemDateClock,
    due_cards,
    grade_card,
)
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
from core.vocab_store import EpisodeLine, VocabStore, WordState
from core.word_analysis import Word, analyse
from core.word_check import CHECK_KEYS, record_answer
from core.word_facts import Facts, WordFacts, import_word_facts

__all__ = [
    "CHECK_KEYS",
    "DAILY_CARD_LIMIT",
    "EpisodeLine",
    "Graded",
    "ReviewCard",
    "SystemDateClock",
    "due_cards",
    "grade_card",
    "OPEN_KINDS",
    "Curriculum",
    "Exercise",
    "ExerciseKind",
    "ExerciseResult",
    "ExerciseStatus",
    "ExerciseStock",
    "Facts",
    "Finished",
    "FoundTopic",
    "FrequencyTable",
    "Grader",
    "GraderError",
    "GraderRunner",
    "GrammarPart",
    "Issue",
    "LanguageToolBusy",
    "LessonExercise",
    "LessonFiles",
    "LessonGrammar",
    "LessonInfo",
    "LessonTopics",
    "LessonWord",
    "Line",
    "NewWord",
    "OpenKind",
    "PickedTopic",
    "Proposal",
    "Refill",
    "Result",
    "SentenceChecker",
    "SentenceResult",
    "SentenceStatus",
    "SentenceToStore",
    "StoredExercise",
    "SubtitleError",
    "Topic",
    "TopicResult",
    "TopicState",
    "TopicStatus",
    "VocabStore",
    "Word",
    "WordFacts",
    "WordState",
    "add_exercises",
    "add_sentences",
    "analyse",
    "build_frequency_table",
    "check_answer",
    "curriculum_gaps",
    "episode_key",
    "extract_subtitles",
    "failed_sentences",
    "find_episode",
    "finish_lesson",
    "import_word_facts",
    "lesson_for_page",
    "new_words",
    "pick_lesson_words",
    "read_lines",
    "record_answer",
    "report_topics",
    "subtitle_file",
    "write_lesson",
]
