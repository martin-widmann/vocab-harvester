"""Frequency table: how often each Base form is heard in German subtitles.

The source is the hermitdave/FrequencyWords German list (OpenSubtitles 2018).
It counts lowercase word forms, one "form count" pair per line. A one-time
build runs each form through spaCy and adds up the counts per Base form.

The keys are case-folded, because the list is lowercase but noun Base forms
are capitalised: "Polizei" finds the count of "polizei".
"""

import sqlite3
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from core.word_analysis import analyse_all

DEFAULT_FREQUENCY = Path(__file__).resolve().parents[2] / "data" / "frequency.sqlite"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS frequency (
    key TEXT PRIMARY KEY,
    count INTEGER NOT NULL
)
"""


def build_frequency_table(source: Iterable[bytes | str], path: Path | str) -> int:
    """Build the frequency table from "form count" lines; give the Base form count.

    A form that spaCy splits into more than one word adds its count to each.
    Names and filler sounds give no Base form, so they are not counted. A
    malformed line raises ValueError and leaves the table from before.
    """
    forms, counts = _read_list(source)
    totals: Counter[str] = Counter()
    for words, count in zip(analyse_all(forms), counts):
        for word in words:
            totals[word.base_form.casefold()] += count
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    try:
        db.execute(_SCHEMA)
        with db:
            db.execute("DELETE FROM frequency")
            db.executemany("INSERT INTO frequency VALUES (?, ?)", totals.items())
        return len(totals)
    finally:
        db.close()


def _read_list(source: Iterable[bytes | str]) -> tuple[list[str], list[int]]:
    forms: list[str] = []
    counts: list[int] = []
    for number, raw in enumerate(source, start=1):
        text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw
        if not text.strip():
            continue
        form, _, count = text.strip().rpartition(" ")
        if not form.strip() or not count.isdigit():
            raise ValueError(f"Line {number} is not 'form count': {text.strip()!r}")
        forms.append(form.strip())
        counts.append(int(count))
    return forms, counts


class FrequencyTable:
    """The built frequency table: Base form -> count."""

    def __init__(self, path: Path | str):
        if not Path(path).is_file():
            raise ValueError(
                f"No frequency table at {path}; build it once with: "
                "python -m core build-frequency"
            )
        self._db = sqlite3.connect(path)
        self._db.execute(_SCHEMA)

    def close(self) -> None:
        self._db.close()

    def count(self, base_form: str) -> int | None:
        """How often the Base form is heard, or None if it is not in the table."""
        row = self._db.execute(
            "SELECT count FROM frequency WHERE key = ?", (base_form.casefold(),)
        ).fetchone()
        return None if row is None else row[0]
