from core import Word, analyse


def base_forms(text):
    return [word.base_form for word in analyse(text)]


def test_a_line_is_reduced_to_base_form_word_type_and_seen_form():
    words = analyse("Die Polizei sucht den Jungen.")

    assert Word("Polizei", "NOUN", "Polizei") in words
    assert Word("suchen", "VERB", "sucht") in words
    assert Word("Junge", "NOUN", "Jungen") in words


def test_separable_verbs_are_joined():
    words = analyse("Er gab nicht auf.")

    assert Word("aufgeben", "VERB", "gab auf") in words
    assert "geben" not in base_forms("Er gab nicht auf.")
    assert "auf" not in base_forms("Er gab nicht auf.")


def test_names_are_filtered_out():
    assert "Mikkel" not in base_forms("Wo ist Mikkel?")
    assert "Martha" not in base_forms("Ich rufe Martha morgen an.")


def test_places_are_filtered_out():
    assert "Berlin" not in base_forms("Gestern war ich in Berlin.")


def test_filler_sounds_are_filtered_out():
    assert base_forms("Äh, ähm... hmm. Ich weiß nicht.") == ["ich", "wissen", "nicht"]
    assert base_forms("Hm.") == []


def test_a_verb_particle_is_only_joined_to_a_verb():
    # spaCy can tag the verb as a noun; the particle must not join it.
    assert "MitBuch" not in base_forms("Nimm das Buch mit!")
    assert "Buch" in base_forms("Nimm das Buch mit!")


def test_common_nouns_that_spacy_sees_as_part_of_a_name_are_kept():
    assert "Mama" in base_forms("Hallo, Mama.")
    assert "Gott" in base_forms("Oh Gott.")
