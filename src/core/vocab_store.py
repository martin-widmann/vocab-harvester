"""Vocab store: the learner's words in one SQLite file."""

import sqlite3
from enum import Enum
from pathlib import Path


class WordState(Enum):
    KNOWN = "Known"
    UNKNOWN = "Unknown"
    TAUGHT = "Taught"
    EXCLUDED = "Excluded"


_STATES = ", ".join(f"'{state.value}'" for state in WordState)

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS words (
    base_form TEXT PRIMARY KEY,
    word_type TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ({_STATES}))
)
"""


class VocabStore:
    """The Base forms the learner has marked, each with its word state."""

    def __init__(self, path: Path | str):
        self._db = sqlite3.connect(path)
        self._db.execute(_SCHEMA)

    def add(self, base_form: str, word_type: str, state: WordState) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO words (base_form, word_type, state) VALUES (?, ?, ?)",
                (base_form, word_type, state.value),
            )

    def contains(self, base_form: str) -> bool:
        row = self._db.execute(
            "SELECT 1 FROM words WHERE base_form = ?", (base_form,)
        ).fetchone()
        return row is not None
