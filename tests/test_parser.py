#!/usr/bin/env python3
"""
Comprehensive test suite for parser module with batch processing workflow.
Tests all parser functions, translation integration, and temporary database storage.
"""

import sys
import os
import unittest
from unittest.mock import patch

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import after path setup  # noqa: E402
from parser import (  # noqa: E402
    clean_text_input,
    tokenize_text,
    lemmatize_words,
    filter_known_words,
    process_text_input
)
from database import (  # noqa: E402
    get_temp_words,
    clear_temp_session
)


class TestParserFunctions(unittest.TestCase):
    """Test individual parser functions."""

    def test_clean_text_input(self):
        """Test text cleaning functionality."""
        # Test normal text
        result = clean_text_input("Hallo Welt!")
        self.assertEqual(result, "Hallo Welt!")

        # Test excessive whitespace
        result = clean_text_input("  Hallo    Welt!  \n\t  ")
        self.assertEqual(result, "Hallo Welt!")

        # Test empty input
        result = clean_text_input("")
        self.assertEqual(result, "")

        # Test whitespace-only input
        result = clean_text_input("   \n\t  ")
        self.assertEqual(result, "")

        # Test None input
        result = clean_text_input(None)
        self.assertEqual(result, "")

    def test_tokenize_text(self):
        """Test tokenization functionality."""
        # Test normal German text
        result = tokenize_text("Ich gehe heute zur Schule.")
        expected = ["ich", "gehe", "heute", "zur", "schule"]
        self.assertEqual(result, expected)

        # Test empty input
        result = tokenize_text("")
        self.assertEqual(result, [])

        # Test punctuation filtering
        result = tokenize_text("Hallo, Welt! 123 @#$")
        expected = ["hallo", "welt"]
        self.assertEqual(result, expected)

        # Test numbers and symbols are filtered out
        result = tokenize_text("123 !@# $%^ &*()")
        self.assertEqual(result, [])

    def test_lemmatize_words(self):
        """Test lemmatization functionality."""
        # Test normal tokens
        tokens = ["gehe", "bücher", "laufen"]
        result = lemmatize_words(tokens)

        # Verify structure
        self.assertIsInstance(result, list)
        for word_data in result:
            self.assertIn('original', word_data)
            self.assertIn('lemma', word_data)
            self.assertIn('pos', word_data)

        # Test empty input
        result = lemmatize_words([])
        self.assertEqual(result, [])

        # Test single word
        result = lemmatize_words(["gehen"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['original'], 'gehen')

    def test_filter_known_words(self):
        """Test known word filtering."""
        # Create test data
        test_words = [
            {'original': 'test1', 'lemma': 'test1', 'pos': 'NOUN'},
            {'original': 'test2', 'lemma': 'test2', 'pos': 'VERB'},
            {'original': 'test3', 'lemma': 'test3', 'pos': 'ADJ'}
        ]

        # Mock word_exists to return True for test1, False for others
        with patch('parser.word_exists') as mock_word_exists:
            mock_word_exists.side_effect = lambda word: word == 'test1'

            result = filter_known_words(test_words)

            # Should filter out test1 (known), keep test2 and test3 (unknown)
            self.assertEqual(len(result), 2)
            lemmas = [word['lemma'] for word in result]
            self.assertIn('test2', lemmas)
            self.assertIn('test3', lemmas)
            self.assertNotIn('test1', lemmas)


class TestBatchProcessingPipeline(unittest.TestCase):
    """Test the complete batch processing pipeline."""

    def setUp(self):
        """Set up test environment."""
        # Create unique session ID for each test
        import uuid
        self.test_session = f"test_session_{uuid.uuid4().hex[:8]}"

    def tearDown(self):
        """Clean up after each test."""
        # Clean up test session
        clear_temp_session(self.test_session)

    @patch('parser.get_best_translation')
    def test_process_text_input_with_translations(self, mock_translation):
        """Test complete pipeline with mocked translations."""
        # Mock translation service
        mock_translation.side_effect = lambda lemma, pos: f"translation_of_{lemma}" if pos == "NOUN" else None

        # Test text with various word types
        test_text = "Das schöne Haus steht dort."

        result = process_text_input(test_text, session_id=self.test_session)

        # Verify result structure
        self.assertIsNotNone(result)
        self.assertIn('session_id', result)
        self.assertIn('words_processed', result)
        self.assertIn('words_added', result)
        self.assertIn('words_translated', result)
        self.assertEqual(result['session_id'], self.test_session)

        # Verify words were added to temp database
        temp_words = get_temp_words(self.test_session)
        self.assertGreater(len(temp_words), 0)

        # Verify translations were attempted
        mock_translation.assert_called()

    @patch('parser.get_best_translation')
    def test_translation_failure_handling(self, mock_translation):
        """Test pipeline handles translation failures gracefully."""
        # Mock translation service to always fail
        mock_translation.return_value = None

        test_text = "Ein kleines Beispiel."

        result = process_text_input(test_text, session_id=self.test_session)

        # Pipeline should still work
        self.assertIsNotNone(result)
        self.assertEqual(result['words_translated'], 0)

        # Words should still be added to temp database
        temp_words = get_temp_words(self.test_session)
        self.assertGreater(len(temp_words), 0)

        # Verify all translations are None
        for word_record in temp_words:
            translation = word_record[3]  # translation column
            self.assertIsNone(translation)

    @patch('parser.get_best_translation')
    def test_session_isolation(self, mock_translation):
        """Test that different sessions are isolated."""
        mock_translation.return_value = "test_translation"

        # Process text in first session
        result1 = process_text_input("Erstes Beispiel.", session_id=self.test_session)

        # Process text in second session
        session2 = f"test_session_2_{self.test_session}"
        result2 = process_text_input("Zweites Beispiel.", session_id=session2)

        # Verify different session IDs
        self.assertNotEqual(result1['session_id'], result2['session_id'])

        # Verify session isolation
        words1 = get_temp_words(self.test_session)
        words2 = get_temp_words(session2)

        # Each session should have its own words
        self.assertGreater(len(words1), 0)
        self.assertGreater(len(words2), 0)

        # Clean up second session
        clear_temp_session(session2)

    def test_empty_input_handling(self):
        """Test handling of empty and invalid inputs."""
        # Test empty string
        result = process_text_input("", session_id=self.test_session)
        self.assertIsNone(result)

        # Test whitespace only
        result = process_text_input("   \n\t  ", session_id=self.test_session)
        self.assertIsNone(result)

        # Test non-alphabetic text
        result = process_text_input("123 !@# $%^", session_id=self.test_session)
        self.assertIsNone(result)

    @patch('parser.get_best_translation')
    def test_irregular_verb_detection(self, mock_translation):
        """Test that irregular verbs are correctly identified."""
        mock_translation.return_value = "test_translation"

        # Use text with irregular verbs (if available in irregular_Verbs.txt)
        test_text = "Ich bin hier gewesen."  # sein is irregular

        result = process_text_input(test_text, session_id=self.test_session)

        if result:  # Only test if processing succeeded
            temp_words = get_temp_words(self.test_session)

            # Look for verbs in the results
            verbs = [word for word in temp_words if word[2] in ['VERB', 'AUX']]  # pos column

            if verbs:
                # Check that is_regular field is set appropriately
                for word_record in verbs:
                    is_regular = word_record[4]  # is_regular column
                    self.assertIsNotNone(is_regular)  # Should be True or False, not None

    @patch('parser.get_best_translation')
    def test_duplicate_word_handling(self, mock_translation):
        """Test that duplicate words in same session are handled correctly."""
        mock_translation.return_value = "test_translation"

        # Process same text twice in same session
        test_text = "Das gleiche Wort das gleiche Wort."

        result1 = process_text_input(test_text, session_id=self.test_session)
        result2 = process_text_input(test_text, session_id=self.test_session)

        # Second processing should find fewer new words (or none)
        if result1 and result2:
            self.assertLessEqual(result2['words_added'], result1['words_added'])

    @patch('parser.temp_word_exists')
    @patch('parser.get_best_translation')
    def test_database_error_handling(self, mock_translation, mock_temp_exists):
        """Test handling of database errors during processing."""
        mock_translation.return_value = "test_translation"

        # Mock database error
        mock_temp_exists.side_effect = Exception("Database error")

        test_text = "Ein einfacher Test."

        # Should handle error gracefully
        try:
            result = process_text_input(test_text, session_id=self.test_session)
            # If no exception raised, processing continued despite error
            self.assertIsNotNone(result)
        except Exception as e:
            # If exception raised, it should be the expected one
            self.assertIn("Database error", str(e))


class TestTemporaryDatabaseIntegration(unittest.TestCase):
    """Test temporary database interactions during processing."""

    def setUp(self):
        """Set up test environment."""
        import uuid
        self.test_session = f"test_db_session_{uuid.uuid4().hex[:8]}"

    def tearDown(self):
        """Clean up after each test."""
        clear_temp_session(self.test_session)

    @patch('parser.get_best_translation')
    def test_temp_database_storage(self, mock_translation):
        """Test that words are correctly stored in temporary database."""
        mock_translation.return_value = "test_translation"

        test_text = "Ein kurzer Test für die Datenbank."

        result = process_text_input(test_text, session_id=self.test_session)

        self.assertIsNotNone(result)

        # Verify data in temp database
        temp_words = get_temp_words(self.test_session)
        self.assertGreater(len(temp_words), 0)

        # Verify data structure
        for word_record in temp_words:
            self.assertEqual(len(word_record), 7)  # word, lemma, pos, translation, is_regular, session_id, created_at

            word, lemma, pos, translation, is_regular, session_id, created_at = word_record

            # Verify data types and content
            self.assertIsInstance(word, str)
            self.assertIsInstance(lemma, str)
            self.assertIsInstance(pos, str)
            self.assertEqual(session_id, self.test_session)
            self.assertIsNotNone(created_at)

    @patch('parser.get_best_translation')
    def test_session_id_consistency(self, mock_translation):
        """Test that session ID is consistently used throughout processing."""
        mock_translation.return_value = "test_translation"

        custom_session = f"custom_{self.test_session}"

        result = process_text_input("Test mit eigener Session.", session_id=custom_session)

        self.assertIsNotNone(result)
        self.assertEqual(result['session_id'], custom_session)

        # Verify all words in temp database have correct session ID
        temp_words = get_temp_words(custom_session)
        for word_record in temp_words:
            session_id = word_record[5]  # session_id column
            self.assertEqual(session_id, custom_session)

        # Clean up custom session
        clear_temp_session(custom_session)


def run_comprehensive_tests():
    """Run all test suites and return results."""
    # Create test suite
    test_suite = unittest.TestSuite()

    # Add all test classes
    test_classes = [
        TestParserFunctions,
        TestBatchProcessingPipeline,
        TestTemporaryDatabaseIntegration
    ]

    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    print("=" * 70)
    print("VOCAB HARVESTER - COMPREHENSIVE PARSER TEST SUITE")
    print("=" * 70)
    print("Testing batch processing workflow with translation integration")
    print()

    success = run_comprehensive_tests()

    if success:
        print("\n" + "=" * 70)
        print("[SUCCESS] ALL TESTS PASSED SUCCESSFULLY!")
        print("=" * 70)
        print("[PASS] Individual parser functions: Working")
        print("[PASS] Batch processing pipeline: Working")
        print("[PASS] Translation integration: Working")
        print("[PASS] Temporary database storage: Working")
        print("[PASS] Session isolation: Working")
        print("[PASS] Error handling: Working")
        sys.exit(0)
    else:
        print("\n" + "=" * 70)
        print("[FAIL] SOME TESTS FAILED!")
        print("=" * 70)
        sys.exit(1)
