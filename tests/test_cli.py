from pathlib import Path

import pytest

from core import VocabStore, WordFacts, WordState
from core.cli import main

EPISODE = Path(__file__).parent / "fixtures" / "Dark" / "S01E01"
KAIKKI_SAMPLE = Path(__file__).parent / "fixtures" / "kaikki-sample.jsonl"


def test_new_words_command_prints_each_new_word_with_its_word_type(tmp_path, capsys):
    db = tmp_path / "vocab.sqlite"
    VocabStore(db).add("Polizei", "NOUN", WordState.KNOWN)

    main(["new-words", str(EPISODE), "--db", str(db)])

    printed = capsys.readouterr().out.splitlines()
    assert "aufgeben (VERB)" in printed
    assert "Höhle (NOUN)" in printed
    assert "Polizei (NOUN)" not in printed


def test_import_word_facts_command_makes_the_kaikki_data_available_offline(
    tmp_path, capsys
):
    facts = tmp_path / "word_facts.sqlite"

    main(["import-word-facts", "--source", str(KAIKKI_SAMPLE), "--facts", str(facts)])

    assert f"Imported 17 word facts entries into {facts}" in capsys.readouterr().out
    assert WordFacts(facts).lookup("Hund", "NOUN").gender == "masculine"


def test_a_failed_import_keeps_the_word_facts_from_before(tmp_path, capsys):
    facts = tmp_path / "word_facts.sqlite"
    main(["import-word-facts", "--source", str(KAIKKI_SAMPLE), "--facts", str(facts)])
    broken = tmp_path / "broken.jsonl"
    broken.write_bytes(KAIKKI_SAMPLE.read_bytes() + b'{"word": "cut off')

    with pytest.raises(SystemExit) as exit:
        main(["import-word-facts", "--source", str(broken), "--facts", str(facts)])

    assert exit.value.code == 1
    assert "no data changed" in capsys.readouterr().err
    assert WordFacts(facts).lookup("Hund", "NOUN").gender == "masculine"
