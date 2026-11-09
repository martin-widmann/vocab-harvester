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
    """The last failed try of an example sentence, and how many tries failed."""

    base_form: str
    number: int
    sentence: str
    problems: list[str]
    failures: int


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
CREATE TABLE IF NOT EXISTS failed_sentences (
    base_form TEXT NOT NULL REFERENCES words (base_form),
    number INTEGER NOT NULL,
    sentence TEXT NOT NULL,
    problems TEXT NOT NULL,
    failures INTEGER NOT NULL,
    PRIMARY KEY (base_form, number)
);
"""


class VocabStore:
    """The Base forms the learner has marked, each with its word state."""

    def __init__(self, path: Path | str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript(_SCHEMA)

    def close(self) -> None:
        self._db.close()

    def add(self, base_form: str, word_type: str, state: WordState) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO words (base_form, word_type, state) VALUES (?, ?, ?)",
                (base_form, word_type, state.value),
            )

    def set_state(self, base_form: str, state: WordState) -> None:
        """Give a stored Base form a new word state."""
        with self._db:
            changed = self._db.execute(
                "UPDATE words SET state = ? WHERE base_form = ?",
                (state.value, base_form),
            ).rowcount
        if not changed:
            raise ValueError(f"{base_form!r} is not in the vocab store")

    def contains(self, base_form: str) -> bool:
        return self.state_of(base_form) is not None

    def state_of(self, base_form: str) -> WordState | None:
        row = self._db.execute(
            "SELECT state FROM words WHERE base_form = ?", (base_form,)
        ).fetchone()
        return None if row is None else WordState(row[0])

    def add_example_sentence(self, base_form: str, number: int, sentence: str) -> None:
        """Store a sentence that passed its check; its failed tries are done with."""
        with self._db:
            self._db.execute(
                "INSERT INTO example_sentences (base_form, number, sentence) "
                "VALUES (?, ?, ?)",
                (base_form, number, sentence),
            )
            self._db.execute(
                "DELETE FROM failed_sentences WHERE base_form = ? AND number = ?",
                (base_form, number),
            )

    def example_sentences(self, base_form: str) -> dict[int, str]:
        """The stored example sentences of a Base form, by their number."""
        rows = self._db.execute(
            "SELECT number, sentence FROM example_sentences WHERE base_form = ? "
            "ORDER BY number",
            (base_form,),
        )
        return dict(rows)

    def add_failed_try(
        self, base_form: str, number: int, sentence: str, problems: list[str]
    ) -> int:
        """Keep a failed try as the last one of its sentence; give the failure count."""
        with self._db:
            self._db.execute(
                "INSERT INTO failed_sentences "
                "(base_form, number, sentence, problems, failures) "
                "VALUES (?, ?, ?, ?, 1) ON CONFLICT (base_form, number) DO UPDATE SET "
                "sentence = excluded.sentence, problems = excluded.problems, "
                "failures = failures + 1",
                (base_form, number, sentence, json.dumps(problems, ensure_ascii=False)),
            )
        return self.failed_tries(base_form, number)

    def failed_tries(self, base_form: str, number: int) -> int:
        """How often example sentence `number` of a Base form failed its check."""
        row = self._db.execute(
            "SELECT failures FROM failed_sentences WHERE base_form = ? AND number = ?",
            (base_form, number),
        ).fetchone()
        return 0 if row is None else row[0]

    def failed_sentences(self) -> list[FailedSentence]:
        """Every example sentence whose last try failed, in the order they first failed."""
        rows = self._db.execute(
            "SELECT base_form, number, sentence, problems, failures "
            "FROM failed_sentences ORDER BY rowid"
        )
        return [
            FailedSentence(base_form, number, sentence, json.loads(problems), failures)
            for base_form, number, sentence, problems, failures in rows
        ]
