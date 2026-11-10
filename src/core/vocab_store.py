"""Vocab store: the learner's words in one SQLite file."""

import json
import sqlite3
from dataclasses import dataclass
from datetime import date
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


@dataclass(frozen=True)
class EpisodeLine:
    """The Line of an Episode where a Lesson word is first heard."""

    episode: str
    number: int
    text: str


@dataclass(frozen=True)
class Teaching:
    """What the Lesson that taught a word says about it, for its reviews.

    `day` is the review day the Lesson was finished on.
    """

    episode: str
    day: date
    seen_form: str | None
    meaning: str | None
    gender: str | None


@dataclass(frozen=True)
class ReviewData:
    """What the vocab store holds for the review of one Taught word.

    `teaching` is None for a word taught before reviews were kept, `line`
    None when the store has no episode Line of the word. `card` is the FSRS
    card as JSON, None before the first review. `reviews` counts the reviews
    done.
    """

    base_form: str
    word_type: str
    teaching: Teaching | None
    line: EpisodeLine | None
    card: str | None
    reviews: int


@dataclass(frozen=True)
class LoggedReview:
    """One vocab review in the review log. `article_right` is None for a non-noun."""

    base_form: str
    day: date
    rating: str
    article_right: bool | None


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
CREATE TABLE IF NOT EXISTS episode_lines (
    base_form TEXT NOT NULL REFERENCES words (base_form),
    episode TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    line_text TEXT NOT NULL,
    PRIMARY KEY (base_form, episode)
);
CREATE TABLE IF NOT EXISTS review_cards (
    base_form TEXT PRIMARY KEY REFERENCES words (base_form),
    episode TEXT,
    taught_on TEXT,
    seen_form TEXT,
    meaning TEXT,
    gender TEXT,
    card TEXT,
    reviews INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS review_log (
    base_form TEXT NOT NULL REFERENCES words (base_form),
    reviewed_at TEXT NOT NULL,
    day TEXT NOT NULL,
    rating TEXT NOT NULL,
    article_right INTEGER
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
            self._set_state(base_form, state)

    def _set_state(self, base_form: str, state: WordState) -> None:
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

    def count_by_state(self) -> dict[WordState, int]:
        """How many Base forms the store holds in each word state."""
        rows = self._db.execute("SELECT state, COUNT(*) FROM words GROUP BY state")
        return {WordState(state): count for state, count in rows}

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

    def keep_episode_line(self, base_form: str, line: EpisodeLine) -> None:
        """Keep the episode Line of a Lesson word, for its first review."""
        with self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO episode_lines "
                "(base_form, episode, line_number, line_text) VALUES (?, ?, ?, ?)",
                (base_form, line.episode, line.number, line.text),
            )

    def teach(self, base_form: str, teaching: Teaching) -> None:
        """Make a stored Base form a Taught word, as the Lesson in `teaching` taught it.

        A word that was taught before keeps its first teaching and its card.
        """
        with self._db:
            self._set_state(base_form, WordState.TAUGHT)
            self._db.execute(
                "INSERT INTO review_cards "
                "(base_form, episode, taught_on, seen_form, meaning, gender) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (base_form) DO NOTHING",
                (
                    base_form, teaching.episode, teaching.day.isoformat(),
                    teaching.seen_form, teaching.meaning, teaching.gender,
                ),
            )

    def review_data(self) -> list[ReviewData]:
        """The review data of every Taught word, in the order they were taught.

        A Taught word with no teaching (taught before reviews were kept)
        comes last.
        """
        rows = self._db.execute(
            """
            SELECT w.base_form, w.word_type, r.episode, r.taught_on, r.seen_form,
                   r.meaning, r.gender, l.line_number, l.line_text, r.card,
                   COALESCE(r.reviews, 0)
            FROM words w
            LEFT JOIN review_cards r ON r.base_form = w.base_form
            LEFT JOIN episode_lines l
                ON l.base_form = w.base_form AND l.episode = r.episode
            WHERE w.state = ?
            ORDER BY r.rowid IS NULL, r.rowid, w.rowid
            """,
            (WordState.TAUGHT.value,),
        )
        found = []
        for (
            base_form, word_type, episode, taught_on, seen_form, meaning, gender,
            number, text, card, reviews,
        ) in rows:
            teaching = None
            line = None
            if episode is not None:
                teaching = Teaching(
                    episode, date.fromisoformat(taught_on), seen_form, meaning, gender
                )
            if text is not None:
                line = EpisodeLine(episode, number, text)
            found.append(ReviewData(base_form, word_type, teaching, line, card, reviews))
        return found

    def save_review(
        self,
        base_form: str,
        card: str,
        reviewed_at: str,
        day: date,
        rating: str,
        article_right: bool | None,
    ) -> None:
        """Save a review of a Taught word: its new FSRS card, and a log entry."""
        with self._db:
            changed = self._db.execute(
                "UPDATE review_cards SET card = ?, reviews = reviews + 1 "
                "WHERE base_form = ?",
                (card, base_form),
            ).rowcount
            if not changed:
                # A word taught before reviews were kept.
                self._db.execute(
                    "INSERT INTO review_cards (base_form, card, reviews) VALUES (?, ?, 1)",
                    (base_form, card),
                )
            self._db.execute(
                "INSERT INTO review_log (base_form, reviewed_at, day, rating, article_right) "
                "VALUES (?, ?, ?, ?, ?)",
                (base_form, reviewed_at, day.isoformat(), rating, article_right),
            )

    def reviewed_on(self, day: date) -> set[str]:
        """The Base forms reviewed on a review day."""
        rows = self._db.execute(
            "SELECT DISTINCT base_form FROM review_log WHERE day = ?", (day.isoformat(),)
        )
        return {base_form for (base_form,) in rows}

    def review_log(self, since: date) -> list[LoggedReview]:
        """The vocab reviews of the review days from `since` on, oldest first."""
        rows = self._db.execute(
            "SELECT base_form, day, rating, article_right FROM review_log "
            "WHERE day >= ? ORDER BY reviewed_at, rowid",
            (since.isoformat(),),
        )
        return [
            LoggedReview(
                base_form,
                date.fromisoformat(day),
                rating,
                None if article_right is None else bool(article_right),
            )
            for base_form, day, rating, article_right in rows
        ]
