"""Vocab store: the learner's words in one SQLite file."""

import sqlite3
from enum import Enum
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "vocab.sqlite"


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
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.execute(_SCHEMA)

    def close(self) -> None:
        self._db.close()

    def add(self, base_form: str, word_type: str, state: WordState) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO words (base_form, word_type, state) VALUES (?, ?, ?)",
                (base_form, word_type, state.value),
            )

    def contains(self, base_form: str) -> bool:
        return self.state_of(base_form) is not None

    def state_of(self, base_form: str) -> WordState | None:
        row = self._db.execute(
            "SELECT state FROM words WHERE base_form = ?", (base_form,)
        ).fetchone()
        return None if row is None else WordState(row[0])
