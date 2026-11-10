"""Word Knowledge Check: the learner marks each New word with one key."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from core.episode import Episode, NewWord, new_words
from core.vocab_store import VocabStore, WordState

CHECK_KEYS = {
    "K": WordState.KNOWN,
    "U": WordState.UNKNOWN,
    "X": WordState.EXCLUDED,
}

WAIT_TIMEOUT = 300.0  # seconds one wait may take
WAIT_INTERVAL = 2.0  # seconds between two looks at the vocab store


class Clock(Protocol):
    def now(self) -> float:
        """Seconds, from any fixed point."""

    def sleep(self, seconds: float) -> None:
        """Wait."""


@dataclass(frozen=True)
class CheckProgress:
    """How far the learner is with the check of an Episode.

    `checked` counts the New words the learner marked during the wait, `left`
    the New words not marked yet. `done` is True when no New word is left.
    """

    done: bool
    checked: int
    left: int


def record_answer(store: VocabStore, word: NewWord, key: str) -> WordState:
    """Store the learner's answer for a New word: K, U or X.

    A word already in the store is not a New word; its state is not changed.
    """
    state = CHECK_KEYS.get(key.upper())
    if state is None:
        raise ValueError(f"Unknown check key {key!r}; use K, U or X")
    if store.contains(word.base_form):
        raise ValueError(f"{word.base_form!r} is already in the vocab store")
    store.add(word.base_form, word.word_type, state)
    return state


def wait_for_check(
    episode: Episode | Path | str,
    store: VocabStore,
    clock: Clock,
    timeout: float = WAIT_TIMEOUT,
    interval: float = WAIT_INTERVAL,
) -> CheckProgress:
    """Wait until the learner has marked every New word of an Episode.

    The learner marks the words on the page, through the web server. This
    looks at the vocab store every `interval` seconds and stops when no New
    word is left, or after `timeout` seconds with the words still left.
    """
    left = new_words(episode, store)
    start = len(left)
    deadline = clock.now() + timeout
    while left and clock.now() < deadline:
        clock.sleep(min(interval, deadline - clock.now()))
        left = [word for word in left if not store.contains(word.base_form)]
    return CheckProgress(done=not left, checked=start - len(left), left=len(left))
