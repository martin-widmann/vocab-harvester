from pathlib import Path

import pytest

from core import (
    CheckProgress,
    NewWord,
    VocabStore,
    WordState,
    new_words,
    mark_unknown,
    record_answer,
    wait_for_check,
)

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


class LearnerOnThePage:
    """A clock: while the tutor waits, the learner marks one word per wait.

    The learner uses the web server's own connection to the vocab file.
    """

    def __init__(self, db_path, keys):
        self.page_store = VocabStore(db_path)
        self.keys = list(keys)
        self.time = 0.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.time

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.time += seconds
        if self.keys:
            left = new_words(DARK / "S01E01", self.page_store)
            record_answer(self.page_store, left[0], self.keys.pop(0))


def test_waiting_for_the_check_ends_when_every_new_word_is_marked(tmp_path):
    db = tmp_path / "vocab.sqlite"
    store = VocabStore(db)
    count = len(new_words(DARK / "S01E01", store))
    learner = LearnerOnThePage(db, ["K", "U", "X"] * count)

    progress = wait_for_check(DARK / "S01E01", store, learner, timeout=600, interval=2)

    assert progress == CheckProgress(done=True, checked=count, left=0)
    assert learner.sleeps == [2] * count
    assert new_words(DARK / "S01E01", store) == []


def test_waiting_for_the_check_stops_after_the_timeout_with_the_words_left(tmp_path):
    db = tmp_path / "vocab.sqlite"
    store = VocabStore(db)
    count = len(new_words(DARK / "S01E01", store))
    learner = LearnerOnThePage(db, ["K", "U"])

    progress = wait_for_check(DARK / "S01E01", store, learner, timeout=10, interval=2)

    assert progress == CheckProgress(done=False, checked=2, left=count - 2)
    assert learner.time == 10


def test_a_check_with_no_new_words_is_done_at_once(tmp_path):
    db = tmp_path / "vocab.sqlite"
    store = VocabStore(db)
    for word in new_words(DARK / "S01E01", store):
        record_answer(store, word, "K")
    learner = LearnerOnThePage(db, [])

    progress = wait_for_check(DARK / "S01E01", store, learner, timeout=600, interval=2)

    assert progress == CheckProgress(done=True, checked=0, left=0)
    assert learner.sleeps == []


@pytest.mark.parametrize(
    "state, error",
    [
        (WordState.UNKNOWN, "already an Unknown word"),
        (WordState.TAUGHT, "Taught word"),
        (WordState.EXCLUDED, "Excluded word"),
    ],
)
def test_only_a_known_word_can_be_marked_unknown(store, state, error):
    store.add("Höhle", "NOUN", state)

    with pytest.raises(ValueError, match=error):
        mark_unknown(store, "Höhle")
    assert store.state_of("Höhle") == state


def test_a_word_not_in_the_vocab_store_cannot_be_marked_unknown(store):
    with pytest.raises(ValueError, match="not in the vocab store"):
        mark_unknown(store, "Höhle")
    assert not store.contains("Höhle")
