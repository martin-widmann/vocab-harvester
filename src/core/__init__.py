"""Core of the German Media Learning system.

The names exported here are the public interface. The MCP server and the
web server are thin adapters over it.
"""

from core.episode import NewWord, find_episode, new_words, subtitle_file
from core.subtitles import Line, SubtitleError, extract_subtitles, read_lines
from core.vocab_store import VocabStore, WordState
from core.word_analysis import Word, analyse
from core.word_check import CHECK_KEYS, record_answer

__all__ = [
    "CHECK_KEYS",
    "Line",
    "NewWord",
    "SubtitleError",
    "VocabStore",
    "Word",
    "WordState",
    "analyse",
    "extract_subtitles",
    "find_episode",
    "new_words",
    "read_lines",
    "record_answer",
    "subtitle_file",
]
