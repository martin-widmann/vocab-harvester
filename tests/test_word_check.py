from pathlib import Path

import pytest

from core import NewWord, VocabStore, WordState, new_words, record_answer

DARK = Path(__file__).parent / "fixtures" / "Dark"


@pytest.fixture
def store(tmp_path):
    return VocabStore(tmp_path / "vocab.sqlite")


@pytest.mark.parametrize(
    "key, state",
    [("K", WordState.KNOWN), ("U", WordState.UNKNOWN), ("X", WordState.EXCLUDED)],
)
def test_each_key_stores_its_word_state(store, key, state):
    record_answer(store, NewWord("Höhle", "NOUN"), key)

    assert store.state_of("Höhle") == state


def base_forms(words):
    return [word.base_form for word in words]


def test_running_the_check_again_does_not_show_words_already_marked(store):
    record_answer(store, NewWord("Polizei", "NOUN"), "K")
    record_answer(store, NewWord("aufgeben", "VERB"), "U")
    record_answer(store, NewWord("Höhle", "NOUN"), "X")

    again = base_forms(new_words(DARK / "S01E01", store))

    assert "Polizei" not in again
    assert "aufgeben" not in again
    assert "Höhle" not in again
    assert "suchen" in again


def test_an_excluded_word_is_never_a_new_word_in_another_episode(store):
    record_answer(store, NewWord("Höhle", "NOUN"), "X")

    assert "Höhle" not in base_forms(new_words(DARK / "S01E02", store))
    assert "warten" in base_forms(new_words(DARK / "S01E02", store))


@pytest.mark.parametrize("state", list(WordState))
def test_an_answer_never_changes_a_word_already_in_the_store(store, state):
    store.add("Höhle", "NOUN", state)

    with pytest.raises(ValueError):
        record_answer(store, NewWord("Höhle", "NOUN"), "K" if state != WordState.KNOWN else "U")

    assert store.state_of("Höhle") == state


def test_keys_are_not_case_sensitive(store):
    record_answer(store, NewWord("Höhle", "NOUN"), "x")

    assert store.state_of("Höhle") == WordState.EXCLUDED


def test_any_other_key_is_rejected(store):
    with pytest.raises(ValueError):
        record_answer(store, NewWord("Höhle", "NOUN"), "T")

    assert store.state_of("Höhle") is None
