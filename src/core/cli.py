"""Command line.

python -m core new-words <episode folder>
python -m core import-word-facts [--source <kaikki .jsonl file or URL>]
python -m core build-frequency [--source <FrequencyWords .txt file or URL>]
"""

import argparse
import http.client
import sqlite3
import urllib.request
from contextlib import closing
from pathlib import Path

from core.episode import new_words
from core.frequency import DEFAULT_FREQUENCY, build_frequency_table
from core.vocab_store import DEFAULT_DB, VocabStore
from core.word_facts import DEFAULT_FACTS, import_word_facts

KAIKKI_URL = "https://kaikki.org/dictionary/German/kaikki.org-dictionary-German.jsonl"
FREQUENCY_URL = (
    "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/"
    "content/2018/de/de_50k.txt"
)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m core")
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser(
        "new-words", help="Print the New words of an Episode folder."
    )
    listing.add_argument("episode_folder", type=Path)
    listing.add_argument("--db", type=Path, default=DEFAULT_DB)
    importing = commands.add_parser(
        "import-word-facts",
        help="Import the kaikki.org German data once, for offline word facts. "
        "This downloads about 1 GB.",
    )
    importing.add_argument(
        "--source",
        default=KAIKKI_URL,
        help="A kaikki .jsonl file or its URL (default: the kaikki.org German extract)",
    )
    importing.add_argument("--facts", type=Path, default=DEFAULT_FACTS)
    building = commands.add_parser(
        "build-frequency",
        help="Build the frequency table of Base forms once, from the "
        "hermitdave/FrequencyWords German subtitle list.",
    )
    building.add_argument(
        "--source",
        default=FREQUENCY_URL,
        help="A FrequencyWords .txt file or its URL "
        "(default: the 50,000 most frequent German forms)",
    )
    building.add_argument("--table", type=Path, default=DEFAULT_FREQUENCY)
    args = parser.parse_args(argv)

    if args.command == "import-word-facts":
        try:
            with closing(_open_source(args.source)) as source:
                count = import_word_facts(source, args.facts)
        except (OSError, ValueError, http.client.HTTPException) as error:
            parser.exit(1, f"error: the import failed, no data changed: {error}\n")
        print(f"Imported {count} word facts entries into {args.facts}")
        return

    if args.command == "build-frequency":
        try:
            with closing(_open_source(args.source)) as source:
                count = build_frequency_table(source, args.table)
        except (OSError, ValueError, sqlite3.Error, http.client.HTTPException) as error:
            parser.exit(1, f"error: the build failed, no data changed: {error}\n")
        print(f"Built the frequency table of {count} Base forms into {args.table}")
        return

    try:
        words = new_words(args.episode_folder, VocabStore(args.db))
    except ValueError as error:
        parser.exit(1, f"error: {error}\n")
    for word in words:
        print(f"{word.base_form} ({word.word_type})")


def _open_source(source: str):
    """The lines of a data file, read from disk or streamed from the web."""
    if source.startswith(("https://", "http://")):
        return urllib.request.urlopen(source)
    return open(source, "rb")
