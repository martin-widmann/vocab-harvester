from pathlib import Path

from core import VocabStore, WordState
from core.cli import main

EPISODE = Path(__file__).parent / "fixtures" / "Dark" / "S01E01"


def test_new_words_command_prints_each_new_word_with_its_word_type(tmp_path, capsys):
    db = tmp_path / "vocab.sqlite"
    VocabStore(db).add("Polizei", "NOUN", WordState.KNOWN)

    main(["new-words", str(EPISODE), "--db", str(db)])

    printed = capsys.readouterr().out.splitlines()
    assert "aufgeben (VERB)" in printed
    assert "Höhle (NOUN)" in printed
    assert "Polizei (NOUN)" not in printed
