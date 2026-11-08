"""Word facts: meaning, gender, plural and verb forms of a Base form.

The facts come from the kaikki.org German extract of English Wiktionary. A
one-time import turns that data into a small SQLite file, so lookups work
offline.
"""

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_FACTS = Path(__file__).resolve().parents[2] / "data" / "word_facts.sqlite"

_GENDERS = ("masculine", "feminine", "neuter")
_MAX_MEANINGS = 3

# The head forms that make the verb forms, by their kaikki tags.
_VERB_FORMS = {
    "present": {"present", "singular", "third-person"},
    "past": {"past"},
    "participle": {"participle", "past"},
    "auxiliary": {"auxiliary"},
}

# Names are not vocabulary.
_SKIPPED_POS = {"name"}

# spaCy word types and the matching kaikki parts of speech.
_POS_OF_WORD_TYPE = {
    "NOUN": "noun",
    "VERB": "verb",
    "AUX": "verb",
    "ADJ": "adj",
    "ADV": "adv",
    "ADP": "prep",
    "PRON": "pron",
    "DET": "det",
    "CCONJ": "conj",
    "SCONJ": "conj",
    "NUM": "num",
    "INTJ": "intj",
    "PART": "particle",
}

# Compounds: each part has at least this many letters, and a part before the
# last one can end in a linking element, as "s" in "Arbeitszimmer".
_MIN_PART = 3
_LINKS = ("s", "es", "n", "en", "e", "er", "ens")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    key TEXT NOT NULL,
    word TEXT NOT NULL,
    pos TEXT NOT NULL,
    meaning TEXT NOT NULL,
    gender TEXT,
    plural TEXT,
    present TEXT,
    past TEXT,
    participle TEXT,
    auxiliary TEXT
);
CREATE INDEX IF NOT EXISTS entries_key ON entries (key);
CREATE TABLE IF NOT EXISTS agent_meanings (
    base_form TEXT PRIMARY KEY,
    meaning TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class Facts:
    """What the word facts data says about one Base form."""

    base_form: str
    meaning: str | None
    meaning_status: str | None
    gender: str | None
    plural: str | None
    verb_forms: dict | None = None
    parts: list[str] = field(default_factory=list)


def import_word_facts(source: Iterable[bytes | str], path: Path | str) -> int:
    """Import kaikki JSON lines into the word facts file; give the entry count."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    try:
        db.executescript(_SCHEMA)
        with db:
            db.execute("DELETE FROM entries")
            count = 0
            for raw in source:
                row = _entry_row(json.loads(raw))
                if row is not None:
                    db.execute(
                        "INSERT INTO entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", row
                    )
                    count += 1
        return count
    finally:
        db.close()


def _entry_row(entry: dict) -> tuple | None:
    word = entry.get("word")
    if not word or entry.get("pos") in _SKIPPED_POS:
        return None
    senses = [sense for sense in entry.get("senses", []) if not _is_form_of(sense)]
    meanings: list[str] = []
    for sense in senses:
        glosses = sense.get("glosses") or []
        if glosses and glosses[-1] not in meanings:
            meanings.append(glosses[-1])
    if not meanings:
        return None
    head_forms = [form for form in entry.get("forms", []) if "source" not in form]
    return (
        word.casefold(),
        word,
        entry.get("pos", ""),
        "; ".join(meanings[:_MAX_MEANINGS]),
        _gender(senses),
        _form(head_forms, {"plural"}),
        *(_form(head_forms, tags) for tags in _VERB_FORMS.values()),
    )


def _is_form_of(sense: dict) -> bool:
    tags = sense.get("tags") or []
    return "form-of" in tags or "alt-of" in tags or bool(sense.get("form_of"))


def _gender(senses: list[dict]) -> str | None:
    for sense in senses:
        for gender in _GENDERS:
            if gender in (sense.get("tags") or []):
                return gender
    return None


def _form(forms: list[dict], tags: set[str]) -> str | None:
    for form in forms:
        if set(form.get("tags") or []) == tags:
            return form.get("form")
    return None


class WordFacts:
    """The imported word facts data."""

    def __init__(self, path: Path | str):
        if not Path(path).is_file():
            raise ValueError(
                f"No word facts at {path}; import them once with: "
                "python -m core import-word-facts"
            )
        self._db = sqlite3.connect(path)
        self._db.executescript(_SCHEMA)

    def close(self) -> None:
        self._db.close()

    def lookup(self, base_form: str, word_type: str | None = None) -> Facts:
        """The facts of a Base form, from the data.

        A noun missing from the data is split into parts found in the data.
        It takes its gender and plural from its last part, but no meaning.
        """
        row = self._entry(base_form, word_type)
        if row is not None:
            _, _, meaning, gender, plural, *forms = row
            verb_forms = dict(zip(_VERB_FORMS, forms)) if any(forms) else None
            return Facts(base_form, meaning, "checked", gender, plural, verb_forms)
        meaning = self._agent_meaning(base_form)
        status = None if meaning is None else "unchecked"
        split = self._split(base_form) if word_type in (None, "NOUN") else None
        if split is None:
            return Facts(base_form, meaning, status, None, None)
        parts, head_length, last = split
        plural = last[4] and base_form[:head_length] + last[4][0].lower() + last[4][1:]
        return Facts(base_form, meaning, status, last[3], plural, parts=parts)

    def add_meaning(self, base_form: str, meaning: str) -> None:
        """Store a meaning an agent wrote for a word the data does not have.

        Lookups mark it "unchecked". Facts from data are never replaced.
        """
        meaning = meaning.strip()
        if not meaning:
            raise ValueError(f"The meaning of {base_form!r} is empty")
        if self._entry(base_form, None) is not None:
            raise ValueError(
                f"{base_form!r} is in the word facts data; its meaning comes from the data"
            )
        with self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO agent_meanings VALUES (?, ?)",
                (base_form, meaning),
            )

    def _agent_meaning(self, base_form: str) -> str | None:
        row = self._db.execute(
            "SELECT meaning FROM agent_meanings WHERE base_form = ?", (base_form,)
        ).fetchone()
        return None if row is None else row[0]

    def _entry(self, base_form: str, word_type: str | None) -> tuple | None:
        """The best entry: same word type first, then same case, then file order."""
        rows = self._db.execute(
            "SELECT word, pos, meaning, gender, plural, present, past, participle, "
            "auxiliary FROM entries WHERE key = ? ORDER BY rowid",
            (base_form.casefold(),),
        ).fetchall()
        if not rows:
            return None
        pos = _POS_OF_WORD_TYPE.get(word_type or "")
        return min(rows, key=lambda row: (row[1] != pos, row[0] != base_form))

    def _split(self, word: str) -> tuple[list[str], int, tuple] | None:
        """Parts of a noun compound, the length of its head and its last entry.

        The longest last part that is a noun in the data wins.
        """
        for head_length in range(_MIN_PART, len(word) - _MIN_PART + 1):
            tail = word[head_length:]
            last = self._entry(tail[0].upper() + tail[1:], "NOUN")
            if last is None or last[1] != "noun":
                continue
            head = self._head_parts(word[:head_length])
            if head is not None:
                return [*head, last[0]], head_length, last
        return None

    def _head_parts(self, head: str) -> list[str] | None:
        for link in ("", *_LINKS):
            if not head.endswith(link):
                continue
            stem = head[: len(head) - len(link)]
            if len(stem) < _MIN_PART:
                continue
            entry = self._entry(stem, None)
            if entry is not None:
                return [entry[0]]
            split = self._split(stem)
            if split is not None:
                return split[0]
        return None
