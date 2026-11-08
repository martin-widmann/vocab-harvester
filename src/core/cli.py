"""Command line.

python -m core new-words <episode folder>
python -m core import-word-facts [--source <kaikki .jsonl file or URL>]
"""

import argparse
import http.client
import urllib.request
from contextlib import closing
from pathlib import Path

from core.episode import new_words
from core.vocab_store import DEFAULT_DB, VocabStore
from core.word_facts import DEFAULT_FACTS, import_word_facts

KAIKKI_URL = "https://kaikki.org/dictionary/German/kaikki.org-dictionary-German.jsonl"


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
    args = parser.parse_args(argv)

    if args.command == "import-word-facts":
        try:
            with closing(_open_source(args.source)) as source:
                count = import_word_facts(source, args.facts)
        except (OSError, ValueError, http.client.HTTPException) as error:
            parser.exit(1, f"error: the import failed, no data changed: {error}\n")
        print(f"Imported {count} word facts entries into {args.facts}")
        return

    try:
        words = new_words(args.episode_folder, VocabStore(args.db))
    except ValueError as error:
        parser.exit(1, f"error: {error}\n")
    for word in words:
        print(f"{word.base_form} ({word.word_type})")


def _open_source(source: str):
    """The lines of a kaikki file, read from disk or streamed from the web."""
    if source.startswith(("https://", "http://")):
        return urllib.request.urlopen(source)
    return open(source, "rb")
