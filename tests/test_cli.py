from contextlib import closing
from pathlib import Path

import pytest

from core import Curriculum, FrequencyTable, Topic, VocabStore, WordFacts, WordState
from core.cli import main

EPISODE = Path(__file__).parent / "fixtures" / "Dark" / "S01E01"
KAIKKI_SAMPLE = Path(__file__).parent / "fixtures" / "kaikki-sample.jsonl"
FREQUENCY_SAMPLE = Path(__file__).parent / "fixtures" / "frequency-sample.txt"


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


def test_build_frequency_command_builds_the_table_once_from_the_list(tmp_path, capsys):
    table = tmp_path / "frequency.sqlite"

    main(["build-frequency", "--source", str(FREQUENCY_SAMPLE), "--table", str(table)])

    assert f"into {table}" in capsys.readouterr().out
    assert FrequencyTable(table).count("geben") == 600


def test_a_failed_build_keeps_the_frequency_table_from_before(tmp_path, capsys):
    table = tmp_path / "frequency.sqlite"
    main(["build-frequency", "--source", str(FREQUENCY_SAMPLE), "--table", str(table)])
    broken = tmp_path / "broken.txt"
    broken.write_bytes(FREQUENCY_SAMPLE.read_bytes() + b"haus\n")

    with pytest.raises(SystemExit) as exit:
        main(["build-frequency", "--source", str(broken), "--table", str(table)])

    assert exit.value.code == 1
    assert "no data changed" in capsys.readouterr().err
    assert FrequencyTable(table).count("geben") == 600


def test_approve_curriculum_command_stores_the_proposal_the_learner_approves(
    tmp_path, capsys
):
    db = tmp_path / "vocab.sqlite"
    with closing(Curriculum(db)) as curriculum:
        number = curriculum.propose(
            [Topic("dativ", "Dativ", "A2"), Topic("konjunktiv-1", "Konjunktiv I", "B2")]
        ).number

    main(["approve-curriculum", str(number), "--db", str(db)])

    assert "Stored the Curriculum: 2 Grammar topics" in capsys.readouterr().out
    with closing(Curriculum(db)) as curriculum:
        assert [status.topic.id for status in curriculum.topics()] == [
            "dativ", "konjunktiv-1",
        ]


def test_approve_curriculum_command_with_no_open_proposal_fails(tmp_path, capsys):
    with pytest.raises(SystemExit) as stopped:
        main(["approve-curriculum", "1", "--db", str(tmp_path / "vocab.sqlite")])

    assert stopped.value.code == 1
    assert "No open proposal" in capsys.readouterr().err
