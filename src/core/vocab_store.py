"""Vocab store: the learner's words in one SQLite file."""

import json
import sqlite3
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "vocab.sqlite"


class WordState(Enum):
    KNOWN = "Known"
    UNKNOWN = "Unknown"
    TAUGHT = "Taught"
    EXCLUDED = "Excluded"


@dataclass(frozen=True)
class FailedSentence:
    """An example sentence that failed its last try; it waits for the learner."""

    base_form: str
    number: int
    sentence: str
    problems: list[str]


_STATES = ", ".join(f"'{state.value}'" for state in WordState)

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS words (
    base_form TEXT PRIMARY KEY,
    word_type TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ({_STATES}))
);
CREATE TABLE IF NOT EXISTS example_sentences (
    base_form TEXT NOT NULL REFERENCES words (base_form),
    number INTEGER NOT NULL,
    sentence TEXT NOT NULL,
    PRIMARY KEY (base_form, number)
);
CREATE TABLE IF NOT EXISTS sentence_tries (
    base_form TEXT NOT NULL REFERENCES words (base_form),
    number INTEGER NOT NULL,
    failures INTEGER NOT NULL,
    PRIMARY KEY (base_form, number)
);
CREATE TABLE IF NOT EXISTS failed_sentences (
    base_form TEXT NOT NULL REFERENCES words (base_form),
    number INTEGER NOT NULL,
    sentence TEXT NOT NULL,
    problems TEXT NOT NULL,
    PRIMARY KEY (base_form, number)
);
"""


class VocabStore:
    """The Base forms the learner has marked, each with its word state."""

    def __init__(self, path: Path | str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.executescript(_SCHEMA)

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

    def add_example_sentence(self, base_form: str, number: int, sentence: str) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO example_sentences (base_form, number, sentence) "
                "VALUES (?, ?, ?)",
                (base_form, number, sentence),
            )

    def example_sentences(self, base_form: str) -> dict[int, str]:
        """The stored example sentences of a Base form, by their number."""
        rows = self._db.execute(
            "SELECT number, sentence FROM example_sentences WHERE base_form = ? "
            "ORDER BY number",
            (base_form,),
        )
        return dict(rows)

    def failed_tries(self, base_form: str, number: int) -> int:
        """How often example sentence `number` of a Base form failed its check."""
        row = self._db.execute(
            "SELECT failures FROM sentence_tries WHERE base_form = ? AND number = ?",
            (base_form, number),
        ).fetchone()
        return 0 if row is None else row[0]

    def add_failed_try(self, base_form: str, number: int) -> int:
        """Count one more failed try; give the new count."""
        with self._db:
            self._db.execute(
                "INSERT INTO sentence_tries (base_form, number, failures) VALUES (?, ?, 1) "
                "ON CONFLICT (base_form, number) DO UPDATE SET failures = failures + 1",
                (base_form, number),
            )
        return self.failed_tries(base_form, number)

    def add_failed_sentence(self, failed: FailedSentence) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO failed_sentences (base_form, number, sentence, problems) "
                "VALUES (?, ?, ?, ?)",
                (
                    failed.base_form,
                    failed.number,
                    failed.sentence,
                    json.dumps(failed.problems, ensure_ascii=False),
                ),
            )

    def failed_sentences(self) -> list[FailedSentence]:
        """The list for the learner: sentences that failed all their tries."""
        rows = self._db.execute(
            "SELECT base_form, number, sentence, problems FROM failed_sentences "
            "ORDER BY rowid"
        )
        return [
            FailedSentence(base_form, number, sentence, json.loads(problems))
            for base_form, number, sentence, problems in rows
        ]

    def is_failed_sentence(self, base_form: str, number: int) -> bool:
        row = self._db.execute(
            "SELECT 1 FROM failed_sentences WHERE base_form = ? AND number = ?",
            (base_form, number),
        ).fetchone()
        return row is not None
