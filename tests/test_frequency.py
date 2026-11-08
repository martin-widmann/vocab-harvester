from pathlib import Path

import pytest

from core import FrequencyTable, build_frequency_table

SAMPLE = Path(__file__).parent / "fixtures" / "frequency-sample.txt"


@pytest.fixture
def table(tmp_path):
    path = tmp_path / "frequency.sqlite"
    with SAMPLE.open("rb") as source:
        build_frequency_table(source, path)
    return FrequencyTable(path)


def test_the_counts_of_all_forms_of_a_base_form_are_added_up(table):
    # gab 300 + gibt 200 + geben 100
    assert table.count("geben") == 600


def test_a_capitalised_noun_base_form_finds_the_count_of_its_lowercase_form(table):
    assert table.count("Polizei") == 50


def test_a_word_missing_from_the_list_has_no_count(table):
    assert table.count("Höhlenforscher") is None


@pytest.mark.parametrize("form", ["Mikkel", "mikkel", "äh"])
def test_names_and_filler_sounds_get_no_count(table, form):
    assert table.count(form) is None
