"""Word Knowledge Check: the learner marks each New word with one key."""

from dataclasses import dataclass
from pathlib import Path

from core.episode import Episode, NewWord, new_words
from core.sentences import Clock
from core.vocab_store import VocabStore, WordState

CHECK_KEYS = {
    "K": WordState.KNOWN,
    "U": WordState.UNKNOWN,
    "X": WordState.EXCLUDED,
}

# Seconds one wait may take. It stays under the 60 seconds an MCP client
# may give a tool call; the tutor calls again while words are left.
WAIT_TIMEOUT = 50.0
WAIT_INTERVAL = 2.0  # seconds between two looks at the vocab store


@dataclass(frozen=True)
class CheckProgress:
    """How far the learner is with the Word Knowledge Check of an Episode.

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
    count_before = len(left)
    deadline = clock.now() + timeout
    while left and clock.now() < deadline:
        clock.sleep(min(interval, deadline - clock.now()))
        left = [word for word in left if not store.contains(word.base_form)]
    return CheckProgress(done=not left, checked=count_before - len(left), left=len(left))


def mark_unknown(store: VocabStore, base_form: str) -> WordState:
    """Make a Known word an Unknown word: the learner says they do not know it.

    It then waits, as every Unknown word, for the Lesson of an Episode where
    it appears. Only a Known word changes; any other word is rejected.
    """
    state = store.state_of(base_form)
    if state is None:
        raise ValueError(
            f"{base_form!r} is not in the vocab store. Give the Base form as "
            "vocab_lookup knows it (a noun starts with a capital letter); a word "
            "that is not in the store comes as a New word in a Word Knowledge Check"
        )
    if state == WordState.UNKNOWN:
        raise ValueError(f"{base_form!r} is already an Unknown word")
    if state == WordState.TAUGHT:
        raise ValueError(f"{base_form!r} is a Taught word: it already gets reviews")
    if state == WordState.EXCLUDED:
        raise ValueError(f"{base_form!r} is an Excluded word, not vocabulary")
    store.set_state(base_form, WordState.UNKNOWN)
    return WordState.UNKNOWN
