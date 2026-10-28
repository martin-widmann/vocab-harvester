"""Word Knowledge Check: the learner marks each New word with one key."""

from core.episode import NewWord
from core.vocab_store import VocabStore, WordState

CHECK_KEYS = {
    "K": WordState.KNOWN,
    "U": WordState.UNKNOWN,
    "X": WordState.EXCLUDED,
}


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
