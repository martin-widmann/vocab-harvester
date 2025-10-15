#!/usr/bin/env python3
"""
Test suite for word approval workflow functions.
Tests approve_word, reject_word, get_pending_words, and clear_session operations.
"""

import sys
import os
import unittest
import uuid

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import after path setup  # noqa: E402
from database import (  # noqa: E402
    approve_word,
    reject_word,
    get_pending_words,
    clear_session,
    add_temp_word,
    word_exists,
    get_word_tags,
    get_temp_words
)


class TestApproveWord(unittest.TestCase):
    """Test approve_word functionality."""

    def setUp(self):
        """Set up test environment with sample temporary words."""
        self.test_session = f"test_approve_{uuid.uuid4().hex[:8]}"

        # Clean up any existing test words from main database first
        import sqlite3
        from database import DB_FILE, TABLE_NAME
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE word IN (?, ?, ?)",
                               ("haus", "schön", "laufen"))
                conn.commit()
        except sqlite3.Error:
            pass

        # Add test words to temporary database
        add_temp_word("haus", "haus", "NOUN", "house", None, self.test_session)
        add_temp_word("schön", "schön", "ADJ", "beautiful", None, self.test_session)
        add_temp_word("laufen", "laufen", "VERB", "run", False, self.test_session)

    def tearDown(self):
        """Clean up test data."""
        clear_session(self.test_session)

        # Also clean up any approved words from main database
        import sqlite3
        from database import DB_FILE, TABLE_NAME
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE word IN (?, ?, ?)",
                               ("haus", "schön", "laufen"))
                conn.commit()
        except sqlite3.Error:
            pass

    def test_approve_word_without_tags(self):
        """Test approving a word without tags."""
        result = approve_word("haus", self.test_session)

        # Should succeed
        self.assertTrue(result)

        # Word should exist in main database
        self.assertTrue(word_exists("haus"))

        # Word should be removed from temp database
        temp_words = get_temp_words(self.test_session)
        temp_lemmas = [word[1] for word in temp_words]
        self.assertNotIn("haus", temp_lemmas)

    def test_approve_word_with_tags(self):
        """Test approving a word with multiple tags."""
        tags = ["noun", "beginner", "common"]
        result = approve_word("schön", self.test_session, tags=tags)

        # Should succeed
        self.assertTrue(result)

        # Word should exist in main database
        self.assertTrue(word_exists("schön"))

        # Word should have all assigned tags
        word_tags = get_word_tags("schön")
        tag_names = [tag[0] for tag in word_tags]

        for expected_tag in tags:
            self.assertIn(expected_tag, tag_names)

    def test_approve_word_not_found(self):
        """Test approving a word that doesn't exist."""
        result = approve_word("nonexistent", self.test_session)

        # Should fail
        self.assertFalse(result)

    def test_approve_word_already_in_main_db(self):
        """Test approving a word that already exists in main database."""
        # First approval should succeed
        result1 = approve_word("laufen", self.test_session)
        self.assertTrue(result1)

        # Add it back to temp for second test
        add_temp_word("laufen", "laufen", "VERB", "run", False, self.test_session)

        # Second approval should fail (already exists)
        result2 = approve_word("laufen", self.test_session)
        self.assertFalse(result2)

        # But it should be removed from temp database
        temp_words = get_temp_words(self.test_session)
        temp_lemmas = [word[1] for word in temp_words]
        self.assertNotIn("laufen", temp_lemmas)

    def test_approve_word_invalid_session(self):
        """Test approving a word from non-existent session."""
        result = approve_word("haus", "invalid_session_12345")

        # Should fail
        self.assertFalse(result)


class TestRejectWord(unittest.TestCase):
    """Test reject_word functionality."""

    def setUp(self):
        """Set up test environment."""
        self.test_session = f"test_reject_{uuid.uuid4().hex[:8]}"

        # Add test words
        add_temp_word("test1", "test1", "NOUN", "test1_trans", None, self.test_session)
        add_temp_word("test2", "test2", "VERB", "test2_trans", True, self.test_session)

    def tearDown(self):
        """Clean up test data."""
        clear_session(self.test_session)

    def test_reject_word_success(self):
        """Test successfully rejecting a word."""
        result = reject_word("test1", self.test_session)

        # Should succeed
        self.assertTrue(result)

        # Word should be removed from temp database
        temp_words = get_temp_words(self.test_session)
        temp_lemmas = [word[1] for word in temp_words]
        self.assertNotIn("test1", temp_lemmas)

    def test_reject_word_not_found(self):
        """Test rejecting a word that doesn't exist."""
        result = reject_word("nonexistent", self.test_session)

        # Should fail
        self.assertFalse(result)

    def test_reject_multiple_words(self):
        """Test rejecting multiple words sequentially."""
        result1 = reject_word("test1", self.test_session)
        result2 = reject_word("test2", self.test_session)

        # Both should succeed
        self.assertTrue(result1)
        self.assertTrue(result2)

        # No words should remain
        temp_words = get_temp_words(self.test_session)
        self.assertEqual(len(temp_words), 0)


class TestGetPendingWords(unittest.TestCase):
    """Test get_pending_words functionality."""

    def setUp(self):
        """Set up test environment."""
        self.test_session1 = f"test_pending_1_{uuid.uuid4().hex[:8]}"
        self.test_session2 = f"test_pending_2_{uuid.uuid4().hex[:8]}"

        # Add words to different sessions
        add_temp_word("word1", "word1", "NOUN", "trans1", None, self.test_session1)
        add_temp_word("word2", "word2", "VERB", "trans2", True, self.test_session1)
        add_temp_word("word3", "word3", "ADJ", "trans3", None, self.test_session2)

    def tearDown(self):
        """Clean up test data."""
        clear_session(self.test_session1)
        clear_session(self.test_session2)

    def test_get_pending_words_specific_session(self):
        """Test getting pending words for a specific session."""
        pending = get_pending_words(self.test_session1)

        # Should return 2 words
        self.assertEqual(len(pending), 2)

        # Should contain correct words
        lemmas = [word[1] for word in pending]
        self.assertIn("word1", lemmas)
        self.assertIn("word2", lemmas)
        self.assertNotIn("word3", lemmas)

    def test_get_pending_words_all_sessions(self):
        """Test getting pending words from all sessions."""
        pending = get_pending_words()

        # Should return at least 3 words (may include others from parallel tests)
        self.assertGreaterEqual(len(pending), 3)

        # Should contain words from both sessions
        lemmas = [word[1] for word in pending]
        self.assertIn("word1", lemmas)
        self.assertIn("word2", lemmas)
        self.assertIn("word3", lemmas)

    def test_get_pending_words_empty_session(self):
        """Test getting pending words from empty session."""
        pending = get_pending_words("empty_session_12345")

        # Should return empty list
        self.assertEqual(len(pending), 0)


class TestClearSession(unittest.TestCase):
    """Test clear_session functionality."""

    def setUp(self):
        """Set up test environment."""
        self.test_session = f"test_clear_{uuid.uuid4().hex[:8]}"

        # Add multiple test words
        for i in range(5):
            add_temp_word(f"word{i}", f"word{i}", "NOUN", f"trans{i}", None, self.test_session)

    def tearDown(self):
        """Clean up test data."""
        clear_session(self.test_session)

    def test_clear_session_success(self):
        """Test successfully clearing a session."""
        # Verify words exist
        pending = get_pending_words(self.test_session)
        self.assertEqual(len(pending), 5)

        # Clear session
        removed = clear_session(self.test_session)

        # Should remove 5 words
        self.assertEqual(removed, 5)

        # Session should be empty
        pending_after = get_pending_words(self.test_session)
        self.assertEqual(len(pending_after), 0)

    def test_clear_empty_session(self):
        """Test clearing an empty session."""
        removed = clear_session("empty_session_12345")

        # Should remove 0 words
        self.assertEqual(removed, 0)

    def test_clear_session_idempotent(self):
        """Test that clearing a session twice is safe."""
        # First clear
        removed1 = clear_session(self.test_session)
        self.assertGreater(removed1, 0)

        # Second clear should remove nothing
        removed2 = clear_session(self.test_session)
        self.assertEqual(removed2, 0)


class TestWorkflowIntegration(unittest.TestCase):
    """Test complete approval workflow integration."""

    def setUp(self):
        """Set up test environment."""
        self.test_session = f"test_workflow_{uuid.uuid4().hex[:8]}"

        # Clean up any existing test words from main database first
        import sqlite3
        from database import DB_FILE, TABLE_NAME
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE word IN (?, ?, ?, ?)",
                               ("baum", "gut", "sein", "schnell"))
                conn.commit()
        except sqlite3.Error:
            pass

        # Add several test words
        add_temp_word("baum", "baum", "NOUN", "tree", None, self.test_session)
        add_temp_word("gut", "gut", "ADJ", "good", None, self.test_session)
        add_temp_word("sein", "sein", "VERB", "be", False, self.test_session)
        add_temp_word("schnell", "schnell", "ADJ", "fast", None, self.test_session)

    def tearDown(self):
        """Clean up test data."""
        clear_session(self.test_session)

        # Clean up approved words from main database
        import sqlite3
        from database import DB_FILE, TABLE_NAME
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE word IN (?, ?, ?, ?)",
                               ("baum", "gut", "sein", "schnell"))
                conn.commit()
        except sqlite3.Error:
            pass

    def test_complete_approval_workflow(self):
        """Test complete workflow: review, approve some, reject others."""
        # Get pending words
        pending = get_pending_words(self.test_session)
        self.assertEqual(len(pending), 4)

        # Approve two words with tags
        approve_word("baum", self.test_session, tags=["noun", "nature"])
        approve_word("sein", self.test_session, tags=["verb", "irregular"])

        # Reject one word
        reject_word("schnell", self.test_session)

        # Check remaining pending words
        pending_after = get_pending_words(self.test_session)
        self.assertEqual(len(pending_after), 1)

        # Verify approved words are in main database
        self.assertTrue(word_exists("baum"))
        self.assertTrue(word_exists("sein"))

        # Verify tags were assigned
        baum_tags = get_word_tags("baum")
        baum_tag_names = [tag[0] for tag in baum_tags]
        self.assertIn("noun", baum_tag_names)
        self.assertIn("nature", baum_tag_names)

    def test_approve_all_then_clear(self):
        """Test approving all words then clearing session."""
        # Get all pending words
        pending = get_pending_words(self.test_session)

        # Approve all
        for word_record in pending:
            lemma = word_record[1]
            approve_word(lemma, self.test_session)

        # Session should be empty
        pending_after = get_pending_words(self.test_session)
        self.assertEqual(len(pending_after), 0)

        # All words should be in main database
        self.assertTrue(word_exists("baum"))
        self.assertTrue(word_exists("gut"))
        self.assertTrue(word_exists("sein"))
        self.assertTrue(word_exists("schnell"))


def run_approval_tests():
    """Run all approval workflow test suites."""
    # Create test suite
    test_suite = unittest.TestSuite()

    # Add all test classes
    test_classes = [
        TestApproveWord,
        TestRejectWord,
        TestGetPendingWords,
        TestClearSession,
        TestWorkflowIntegration
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
    print("VOCAB HARVESTER - WORD APPROVAL WORKFLOW TEST SUITE")
    print("=" * 70)
    print("Testing approve_word, reject_word, get_pending_words, clear_session")
    print()

    success = run_approval_tests()

    if success:
        print("\n" + "=" * 70)
        print("[SUCCESS] ALL APPROVAL WORKFLOW TESTS PASSED!")
        print("=" * 70)
        print("[PASS] approve_word function: Working")
        print("[PASS] reject_word function: Working")
        print("[PASS] get_pending_words function: Working")
        print("[PASS] clear_session function: Working")
        print("[PASS] Workflow integration: Working")
        sys.exit(0)
    else:
        print("\n" + "=" * 70)
        print("[FAIL] SOME TESTS FAILED!")
        print("=" * 70)
        sys.exit(1)
