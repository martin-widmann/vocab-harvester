"""
Test suite for article extraction functionality in parser.py

Tests that German nouns are automatically prepended with appropriate articles
(der/die/das) based on gender extracted from spaCy.
"""

import sys
import os

# Add src directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from parser import get_article_from_gender, lemmatize_words


def test_get_article_from_gender():
    """Test that gender values map correctly to German articles."""
    # Test masculine
    assert get_article_from_gender(['Masc']) == 'der'

    # Test feminine
    assert get_article_from_gender(['Fem']) == 'die'

    # Test neuter
    assert get_article_from_gender(['Neut']) == 'das'

    # Test empty list
    assert get_article_from_gender([]) is None

    # Test None
    assert get_article_from_gender(None) is None

    # Test unknown gender
    assert get_article_from_gender(['Unknown']) is None

    print("[PASS] test_get_article_from_gender passed")


def test_lemmatize_with_articles_masculine():
    """Test that masculine nouns get 'der' article."""
    tokens = ['Mann', 'Tisch', 'Hund']
    result = lemmatize_words(tokens)

    # Find nouns in results
    nouns = [item for item in result if item['pos'] == 'NOUN']

    # Check that we have nouns
    assert len(nouns) > 0, "No nouns found in result"

    # Check that masculine nouns have 'der'
    for noun in nouns:
        lemma = noun['lemma']
        if 'mann' in lemma or 'tisch' in lemma or 'hund' in lemma:
            assert lemma.startswith('der '), f"Expected 'der' prefix for {lemma}"

    print("[PASS] test_lemmatize_with_articles_masculine passed")


def test_lemmatize_with_articles_feminine():
    """Test that feminine nouns get 'die' article."""
    tokens = ['Frau', 'Katze']
    result = lemmatize_words(tokens)

    # Find nouns in results
    nouns = [item for item in result if item['pos'] == 'NOUN']

    # Check that we have nouns
    assert len(nouns) > 0, "No nouns found in result"

    # Check that feminine nouns have 'die'
    for noun in nouns:
        lemma = noun['lemma']
        if 'frau' in lemma or 'katze' in lemma:
            assert lemma.startswith('die '), f"Expected 'die' prefix for {lemma}"

    print("[PASS] test_lemmatize_with_articles_feminine passed")


def test_lemmatize_with_articles_neuter():
    """Test that neuter nouns get 'das' article."""
    tokens = ['Kind', 'Buch', 'Haus']
    result = lemmatize_words(tokens)

    # Find nouns in results
    nouns = [item for item in result if item['pos'] == 'NOUN']

    # Check that we have nouns
    assert len(nouns) > 0, "No nouns found in result"

    # Check that neuter nouns have 'das'
    for noun in nouns:
        lemma = noun['lemma']
        if 'kind' in lemma or 'buch' in lemma or 'haus' in lemma:
            assert lemma.startswith('das '), f"Expected 'das' prefix for {lemma}"

    print("[PASS] test_lemmatize_with_articles_neuter passed")


def test_lemmatize_mixed_pos():
    """Test that only nouns get articles, not verbs or other POS."""
    tokens = ['Mann', 'geht', 'schnell']
    result = lemmatize_words(tokens)

    # Check nouns have articles
    nouns = [item for item in result if item['pos'] == 'NOUN']
    for noun in nouns:
        assert ' ' in noun['lemma'], f"Noun {noun['lemma']} should have article"

    # Check verbs don't have articles
    verbs = [item for item in result if item['pos'] == 'VERB']
    for verb in verbs:
        assert not verb['lemma'].startswith('der '), f"Verb {verb['lemma']} should not have article"
        assert not verb['lemma'].startswith('die '), f"Verb {verb['lemma']} should not have article"
        assert not verb['lemma'].startswith('das '), f"Verb {verb['lemma']} should not have article"

    print("[PASS] test_lemmatize_mixed_pos passed")


def test_lemmatize_with_full_sentence():
    """Test article extraction with a complete German sentence."""
    # "The man eats bread" - Mann is masculine, Brot is neuter
    tokens = ['Der', 'Mann', 'isst', 'Brot']
    result = lemmatize_words(tokens)

    # Find the nouns
    mann_items = [item for item in result if 'mann' in item['lemma'].lower()]
    brot_items = [item for item in result if 'brot' in item['lemma'].lower()]

    # Mann should have 'der'
    assert len(mann_items) > 0, "Mann not found"
    assert mann_items[0]['lemma'].startswith('der '), f"Expected 'der mann', got {mann_items[0]['lemma']}"

    # Brot should have 'das'
    assert len(brot_items) > 0, "Brot not found"
    assert brot_items[0]['lemma'].startswith('das '), f"Expected 'das brot', got {brot_items[0]['lemma']}"

    print("[PASS] test_lemmatize_with_full_sentence passed")


def run_all_tests():
    """Run all article extraction tests."""
    print("\n" + "=" * 80)
    print("RUNNING ARTICLE EXTRACTION TESTS")
    print("=" * 80 + "\n")

    tests = [
        test_get_article_from_gender,
        test_lemmatize_with_articles_masculine,
        test_lemmatize_with_articles_feminine,
        test_lemmatize_with_articles_neuter,
        test_lemmatize_mixed_pos,
        test_lemmatize_with_full_sentence,
    ]

    failed = []
    for test in tests:
        try:
            test()
        except AssertionError as e:
            print(f"[FAIL] {test.__name__} FAILED: {e}")
            failed.append(test.__name__)
        except Exception as e:
            print(f"[ERROR] {test.__name__} ERROR: {e}")
            failed.append(test.__name__)

    print("\n" + "=" * 80)
    if failed:
        print(f"FAILED: {len(failed)} test(s) failed")
        for name in failed:
            print(f"  - {name}")
        print("=" * 80)
        return False
    else:
        print(f"SUCCESS: All {len(tests)} tests passed!")
        print("=" * 80)
        return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
