from pathlib import Path

from core import NewWord, VocabStore, WordState, new_words

EPISODE = Path(__file__).parent / "fixtures" / "Dark" / "S01E01"


def test_new_words_are_the_base_forms_of_the_episode_in_story_order(tmp_path):
    store = VocabStore(tmp_path / "vocab.sqlite")

    assert new_words(EPISODE, store) == [
        NewWord("wo", "SCONJ"),
        NewWord("sein", "AUX"),
        NewWord("der", "DET"),
        NewWord("Polizei", "NOUN"),
        NewWord("suchen", "VERB"),
        NewWord("Junge", "NOUN"),
        NewWord("in", "ADP"),
        NewWord("Höhle", "NOUN"),
        NewWord("er", "PRON"),
        NewWord("aufgeben", "VERB"),
        NewWord("nicht", "PART"),
        NewWord("wohnen", "VERB"),
    ]


def test_base_forms_in_the_vocab_store_are_not_new_words(tmp_path):
    store = VocabStore(tmp_path / "vocab.sqlite")
    store.add("Polizei", "NOUN", WordState.KNOWN)
    store.add("aufgeben", "VERB", WordState.UNKNOWN)
    store.add("wohnen", "VERB", WordState.TAUGHT)
    store.add("der", "DET", WordState.EXCLUDED)

    base_forms = [word.base_form for word in new_words(EPISODE, store)]

    assert "Polizei" not in base_forms
    assert "aufgeben" not in base_forms
    assert "wohnen" not in base_forms
    assert "der" not in base_forms
    assert "suchen" in base_forms


def test_the_vocab_store_keeps_its_words_after_it_is_opened_again(tmp_path):
    VocabStore(tmp_path / "vocab.sqlite").add("Höhle", "NOUN", WordState.KNOWN)

    store = VocabStore(tmp_path / "vocab.sqlite")

    assert "Höhle" not in [word.base_form for word in new_words(EPISODE, store)]
