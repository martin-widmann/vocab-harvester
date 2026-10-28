"""Command line: python -m core new-words <episode folder>."""

import argparse
from pathlib import Path

from core.episode import new_words
from core.vocab_store import VocabStore

DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "vocab.sqlite"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m core")
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser(
        "new-words", help="Print the New words of an Episode folder."
    )
    listing.add_argument("episode_folder", type=Path)
    listing.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args(argv)

    args.db.parent.mkdir(parents=True, exist_ok=True)
    for word in new_words(args.episode_folder, VocabStore(args.db)):
        print(f"{word.base_form} ({word.word_type})")
