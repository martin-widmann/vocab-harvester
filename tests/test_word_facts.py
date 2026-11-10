from pathlib import Path

import pytest

from core import WordFacts, import_word_facts

SAMPLE = Path(__file__).parent / "fixtures" / "kaikki-sample.jsonl"


@pytest.fixture
def facts_path(tmp_path):
    path = tmp_path / "word_facts.sqlite"
    with SAMPLE.open("rb") as source:
        import_word_facts(source, path)
    return path


@pytest.fixture
def facts(facts_path):
    return WordFacts(facts_path)


def test_lookup_gives_meaning_gender_and_plural_of_a_noun(facts):
    hund = facts.lookup("Hund", "NOUN")

    assert hund.meaning == "dog (Canis lupus familiaris); hound; male dog"
    assert hund.meaning_status == "checked"
    assert hund.gender == "masculine"
    assert hund.plural == "Hunde"
    assert hund.verb_forms is None
    assert hund.parts == []


def test_lookup_gives_the_verb_forms_of_a_verb(facts):
    geben = facts.lookup("geben", "VERB")

    assert geben.meaning == "to give; to deal (cards)"
    assert geben.gender is None
    assert geben.plural is None
    assert geben.verb_forms == {
        "present": "gibt",
        "past": "gab",
        "participle": "gegeben",
        "auxiliary": "haben",
    }


def test_the_verb_forms_of_a_separable_verb_keep_the_particle(facts):
    assert facts.lookup("aufgeben", "VERB").verb_forms == {
        "present": "gibt auf",
        "past": "gab auf",
        "participle": "aufgegeben",
        "auxiliary": "haben",
    }


def test_the_word_type_picks_the_entry_when_a_noun_and_a_verb_share_a_spelling(facts):
    assert facts.lookup("Essen", "NOUN").gender == "neuter"
    assert facts.lookup("essen", "VERB").verb_forms["past"] == "aß"
    assert facts.lookup("essen", "NOUN").meaning == "food; meal"


def test_a_noun_with_no_plural_has_none_as_plural(facts):
    durst = facts.lookup("Durst", "NOUN")

    assert durst.gender == "masculine"
    assert durst.plural is None


@pytest.mark.parametrize("base_form", ["gab", "Paris", "Quatsch"])
def test_names_inflected_forms_and_missing_words_have_no_facts(facts, base_form):
    missing = facts.lookup(base_form, "NOUN")

    assert missing.meaning is None
    assert missing.meaning_status is None
    assert missing.gender is None
    assert missing.plural is None
    assert missing.verb_forms is None


def test_a_compound_missing_from_the_data_is_split_and_takes_the_gender_of_its_last_part(facts):
    compound = facts.lookup("Mordkommission", "NOUN")

    assert compound.parts == ["Mord", "Kommission"]
    assert compound.gender == "feminine"
    assert compound.plural == "Mordkommissionen"
    assert compound.meaning is None
    assert compound.meaning_status is None


@pytest.mark.parametrize(
    "base_form, parts, gender, plural",
    [
        ("Arbeitszimmer", ["Arbeit", "Zimmer"], "neuter", "Arbeitszimmer"),
        ("Hundehöhle", ["Hund", "Höhle"], "feminine", "Hundehöhlen"),
        ("Hausaufgabe", ["Haus", "Aufgabe"], "feminine", "Hausaufgaben"),
        ("Großstadt", ["groß", "Stadt"], "feminine", "Großstädte"),
        (
            "Mordkommissionsarbeit",
            ["Mord", "Kommission", "Arbeit"],
            "feminine",
            "Mordkommissionsarbeiten",
        ),
    ],
)
def test_compound_parts_can_have_a_linking_letter_or_be_compounds_too(
    facts, base_form, parts, gender, plural
):
    compound = facts.lookup(base_form, "NOUN")

    assert (compound.parts, compound.gender, compound.plural) == (parts, gender, plural)


@pytest.mark.parametrize(
    "base_form, word_type", [("Quatsch", "NOUN"), ("Hundstag", "NOUN"), ("mordgehen", "VERB")]
)
def test_a_word_that_does_not_split_into_known_parts_has_no_parts(
    facts, base_form, word_type
):
    assert facts.lookup(base_form, word_type).parts == []


def test_a_meaning_from_an_agent_is_stored_and_marked_unchecked(facts_path):
    WordFacts(facts_path).add_meaning("Mordkommission", "homicide squad")

    compound = WordFacts(facts_path).lookup("Mordkommission", "NOUN")

    assert compound.meaning == "homicide squad"
    assert compound.meaning_status == "unchecked"
    assert compound.gender == "feminine"
    assert compound.parts == ["Mord", "Kommission"]


def test_a_new_meaning_from_an_agent_replaces_the_old_one(facts):
    facts.add_meaning("Mordkommission", "murder commission")
    facts.add_meaning("Mordkommission", "  homicide squad ")

    assert facts.lookup("Mordkommission", "NOUN").meaning == "homicide squad"


def test_meanings_from_an_agent_stay_after_a_new_import(facts_path):
    WordFacts(facts_path).add_meaning("Mordkommission", "homicide squad")

    with SAMPLE.open("rb") as source:
        import_word_facts(source, facts_path)

    assert WordFacts(facts_path).lookup("Mordkommission").meaning == "homicide squad"


def test_the_data_meaning_wins_over_an_agent_meaning_once_the_data_has_the_word(tmp_path):
    path = tmp_path / "word_facts.sqlite"
    import_word_facts([], path)
    WordFacts(path).add_meaning("Hund", "puppy")

    with SAMPLE.open("rb") as source:
        import_word_facts(source, path)

    hund = WordFacts(path).lookup("Hund", "NOUN")
    assert hund.meaning_status == "checked"
    assert hund.meaning.startswith("dog")


def test_an_agent_cannot_give_a_meaning_for_a_word_the_data_has(facts):
    with pytest.raises(ValueError, match="Hund"):
        facts.add_meaning("Hund", "cat")

    assert facts.lookup("Hund", "NOUN").meaning_status == "checked"


def test_an_empty_meaning_is_rejected(facts):
    with pytest.raises(ValueError, match="empty"):
        facts.add_meaning("Mordkommission", "  ")


def test_word_facts_that_were_never_imported_are_an_error_that_tells_how_to_import(tmp_path):
    path = tmp_path / "word_facts.sqlite"

    with pytest.raises(ValueError, match="import-word-facts"):
        WordFacts(path)

    assert not path.exists()


def test_blank_lines_in_the_kaikki_data_are_skipped(tmp_path):
    path = tmp_path / "word_facts.sqlite"
    lines = SAMPLE.read_bytes().splitlines(keepends=True)

    count = import_word_facts([lines[1], b"\n", b"  \r\n", lines[2]], path)

    assert count == 2


def test_splitting_a_long_word_of_many_short_parts_stays_fast(tmp_path):
    path = tmp_path / "word_facts.sqlite"
    entry = '{{"word": "{0}", "pos": "noun", "senses": [{{"glosses": ["x"], "tags": ["neuter"]}}]}}'
    nouns = ["Abe", "Bea", "Eab", "Abeb", "Beab"]
    import_word_facts([entry.format(noun) for noun in nouns], path)
    facts = WordFacts(path)
    calls = 0
    real_entry = facts._entry

    def counted_entry(*args):
        nonlocal calls
        calls += 1
        return real_entry(*args)

    facts._entry = counted_entry

    compound = facts.lookup("Abeabeabeabeabeabeabeabeabeabeabeabeabeabeabez", "NOUN")

    assert compound.parts == []
    assert calls < 20_000
