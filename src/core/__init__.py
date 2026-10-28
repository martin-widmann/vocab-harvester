"""Core of the German Media Learning system.

The names exported here are the public interface. The MCP server and the
web server are thin adapters over it.
"""

from core.episode import NewWord, new_words
from core.subtitles import Line, read_lines
from core.vocab_store import VocabStore, WordState
from core.word_analysis import Word, analyse

__all__ = [
    "Line",
    "NewWord",
    "VocabStore",
    "Word",
    "WordState",
    "analyse",
    "new_words",
    "read_lines",
]
