#!/usr/bin/env python3
"""
Comprehensive tests for temporary database operations (Issue #8).

Tests cover:
- approve_word() functionality with and without tags
- reject_word() functionality
- get_pending_words() with session filtering
- clear_session() functionality
- Error handling for invalid operations
- Database integrity during transfer operations
- Concurrent session handling
"""

import sys
import os
import unittest
import uuid
import sqlite3

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
    get_temp_words,
    temp_word_exists,
    remove_temp_word,
    clear_temp_session,
    connect_db,
    DB_FILE,
    TABLE_NAME
)


class TestApproveWordOperations(unittest.TestCase):
    """Test approve_word() functionality with and without tags."""

    def setUp(self):
        """Set up test environment with sample temporary words."""
        self.test_session = f"test_approve_{uuid.uuid4().hex[:8]}"

        # Clean up any existing test words from main database first
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE word IN (?, ?, ?, ?)",
                               ("testhaus", "testschön", "testlaufen", "testgut"))
                conn.commit()
        except sqlite3.Error:
            pass

        # Add test words to temporary database
        add_temp_word("testhaus", "testhaus", "NOUN", "house", True, self.test_session)
        add_temp_word("testschön", "testschön", "ADJ", "beautiful", True, self.test_session)
        add_temp_word("testlaufen", "testlaufen", "VERB", "run", False, self.test_session)
        add_temp_word("testgut", "testgut", "ADJ", "good", True, self.test_session)

    def tearDown(self):
        """Clean up test data."""
        clear_session(self.test_session)

        # Also clean up any approved words from main database
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE word IN (?, ?, ?, ?)",
                               ("testhaus", "testschön", "testlaufen", "testgut"))
                conn.commit()
        except sqlite3.Error:
            pass

    def test_approve_word_without_tags(self):
        """Test approving a word without tags."""
        result = approve_word("testhaus", self.test_session)

        # Should succeed
        self.assertTrue(result, "approve_word should return True on success")

        # Word should exist in main database
        self.assertTrue(word_exists("testhaus"), "Approved word should exist in main database")

        # Word should be removed from temp database
        temp_words = get_temp_words(self.test_session)
        temp_lemmas = [word[1] for word in temp_words]
        self.assertNotIn("testhaus", temp_lemmas, "Approved word should be removed from temp database")

    def test_approve_word_with_single_tag(self):
        """Test approving a word with a single tag."""
        tags = ["test-single-tag"]
        result = approve_word("testschön", self.test_session, tags=tags)

        # Should succeed
        self.assertTrue(result, "approve_word with tags should return True on success")

        # Word should exist in main database
        self.assertTrue(word_exists("testschön"), "Approved word should exist in main database")

        # Word should have the assigned tag
        word_tags = get_word_tags("testschön")
        tag_names = [tag[0] for tag in word_tags]
        self.assertIn("test-single-tag", tag_names, "Tag should be assigned to approved word")

    def test_approve_word_with_multiple_tags(self):
        """Test approving a word with multiple tags."""
        tags = ["test-noun", "test-beginner", "test-common"]
        result = approve_word("testlaufen", self.test_session, tags=tags)

        # Should succeed
        self.assertTrue(result, "approve_word with multiple tags should return True on success")

        # Word should exist in main database
        self.assertTrue(word_exists("testlaufen"), "Approved word should exist in main database")

        # Word should have all assigned tags
        word_tags = get_word_tags("testlaufen")
        tag_names = [tag[0] for tag in word_tags]

        for expected_tag in tags:
            self.assertIn(expected_tag, tag_names, f"Tag '{expected_tag}' should be assigned to approved word")

    def test_approve_word_not_found(self):
        """Test approving a word that doesn't exist (error handling)."""
        result = approve_word("nonexistent", self.test_session)

        # Should fail gracefully
        self.assertFalse(result, "approve_word should return False for non-existent word")

    def test_approve_word_already_in_main_db(self):
        """Test database integrity when approving a word that already exists."""
        # First approval should succeed
        result1 = approve_word("testgut", self.test_session)
        self.assertTrue(result1, "First approval should succeed")

        # Add it back to temp for second test
        add_temp_word("testgut", "testgut", "ADJ", "good", True, self.test_session)

        # Second approval should fail (already exists)
        result2 = approve_word("testgut", self.test_session)
        self.assertFalse(result2, "Second approval should fail (word already exists)")

        # But it should still be removed from temp database (cleanup)
        temp_words = get_temp_words(self.test_session)
        temp_lemmas = [word[1] for word in temp_words]
        self.assertNotIn("testgut", temp_lemmas, "Duplicate word should be cleaned from temp database")

    def test_approve_word_invalid_session(self):
        """Test error handling for invalid session."""
        result = approve_word("testhaus", "invalid_session_xyz")

        # Should fail gracefully
        self.assertFalse(result, "approve_word should return False for invalid session")


class TestRejectWordOperations(unittest.TestCase):
    """Test reject_word() functionality."""

    def setUp(self):
        """Set up test environment."""
        self.test_session = f"test_reject_{uuid.uuid4().hex[:8]}"

        # Add test words
        add_temp_word("rejecttest1", "rejecttest1", "NOUN", "test1_trans", True, self.test_session)
        add_temp_word("rejecttest2", "rejecttest2", "VERB", "test2_trans", True, self.test_session)
        add_temp_word("rejecttest3", "rejecttest3", "ADJ", "test3_trans", False, self.test_session)

    def tearDown(self):
        """Clean up test data."""
        clear_session(self.test_session)

    def test_reject_word_success(self):
        """Test successfully rejecting a word."""
        result = reject_word("rejecttest1", self.test_session)

        # Should succeed
        self.assertTrue(result, "reject_word should return True on success")

        # Word should be removed from temp database
        temp_words = get_temp_words(self.test_session)
        temp_lemmas = [word[1] for word in temp_words]
        self.assertNotIn("rejecttest1", temp_lemmas, "Rejected word should be removed from temp database")

    def test_reject_word_not_found(self):
        """Test error handling when rejecting non-existent word."""
        result = reject_word("nonexistent", self.test_session)

        # Should fail gracefully
        self.assertFalse(result, "reject_word should return False for non-existent word")

    def test_reject_multiple_words_sequentially(self):
        """Test rejecting multiple words in sequence."""
        result1 = reject_word("rejecttest1", self.test_session)
        result2 = reject_word("rejecttest2", self.test_session)
        result3 = reject_word("rejecttest3", self.test_session)

        # All should succeed
        self.assertTrue(result1, "First rejection should succeed")
        self.assertTrue(result2, "Second rejection should succeed")
        self.assertTrue(result3, "Third rejection should succeed")

        # No words should remain
        temp_words = get_temp_words(self.test_session)
        self.assertEqual(len(temp_words), 0, "All rejected words should be removed")

    def test_reject_word_invalid_session(self):
        """Test error handling for rejecting word in invalid session."""
        result = reject_word("rejecttest1", "invalid_session_xyz")

        # Should fail gracefully
        self.assertFalse(result, "reject_word should return False for invalid session")


class TestGetPendingWords(unittest.TestCase):
    """Test get_pending_words() with session filtering."""

    def setUp(self):
        """Set up test environment with multiple sessions."""
        self.test_session1 = f"test_pending_1_{uuid.uuid4().hex[:8]}"
        self.test_session2 = f"test_pending_2_{uuid.uuid4().hex[:8]}"

        # Add words to different sessions
        add_temp_word("pending1", "pending1", "NOUN", "trans1", True, self.test_session1)
        add_temp_word("pending2", "pending2", "VERB", "trans2", True, self.test_session1)
        add_temp_word("pending3", "pending3", "ADJ", "trans3", False, self.test_session1)
        add_temp_word("pending4", "pending4", "NOUN", "trans4", True, self.test_session2)
        add_temp_word("pending5", "pending5", "VERB", "trans5", False, self.test_session2)

    def tearDown(self):
        """Clean up test data."""
        clear_session(self.test_session1)
        clear_session(self.test_session2)

    def test_get_pending_words_specific_session(self):
        """Test getting pending words for a specific session."""
        pending = get_pending_words(self.test_session1)

        # Should return exactly 3 words from session 1
        self.assertEqual(len(pending), 3, "Should return 3 words from session 1")

        # Should contain correct words
        lemmas = [word[1] for word in pending]
        self.assertIn("pending1", lemmas, "Should contain pending1")
        self.assertIn("pending2", lemmas, "Should contain pending2")
        self.assertIn("pending3", lemmas, "Should contain pending3")
        self.assertNotIn("pending4", lemmas, "Should not contain words from other session")
        self.assertNotIn("pending5", lemmas, "Should not contain words from other session")

    def test_get_pending_words_another_session(self):
        """Test getting pending words for another session."""
        pending = get_pending_words(self.test_session2)

        # Should return exactly 2 words from session 2
        self.assertEqual(len(pending), 2, "Should return 2 words from session 2")

        # Should contain correct words
        lemmas = [word[1] for word in pending]
        self.assertIn("pending4", lemmas, "Should contain pending4")
        self.assertIn("pending5", lemmas, "Should contain pending5")
        self.assertNotIn("pending1", lemmas, "Should not contain words from other session")

    def test_get_pending_words_all_sessions(self):
        """Test getting pending words from all sessions."""
        pending = get_pending_words()

        # Should return at least 5 words (may include others from parallel tests)
        self.assertGreaterEqual(len(pending), 5, "Should return at least 5 words from all sessions")

        # Should contain words from both sessions
        lemmas = [word[1] for word in pending]
        self.assertIn("pending1", lemmas, "Should contain words from session 1")
        self.assertIn("pending4", lemmas, "Should contain words from session 2")

    def test_get_pending_words_empty_session(self):
        """Test getting pending words from empty session."""
        pending = get_pending_words("empty_session_xyz")

        # Should return empty list
        self.assertEqual(len(pending), 0, "Should return empty list for empty session")

    def test_get_pending_words_data_structure(self):
        """Test that pending words return correct data structure."""
        pending = get_pending_words(self.test_session1)

        # Each word should have 7 fields
        for word_data in pending:
            self.assertEqual(len(word_data), 7, "Each word should have 7 fields")
            # Fields: word, lemma, pos, translation, is_regular, session_id, created_at
            self.assertIsInstance(word_data[0], str, "word should be string")
            self.assertIsInstance(word_data[1], str, "lemma should be string")
            self.assertIsInstance(word_data[2], str, "pos should be string")
            self.assertEqual(word_data[5], self.test_session1, "session_id should match")


class TestClearSession(unittest.TestCase):
    """Test clear_session() functionality."""

    def setUp(self):
        """Set up test environment."""
        self.test_session = f"test_clear_{uuid.uuid4().hex[:8]}"

        # Add multiple test words
        for i in range(7):
            add_temp_word(f"clearword{i}", f"clearword{i}", "NOUN", f"trans{i}", True, self.test_session)

    def tearDown(self):
        """Clean up test data."""
        clear_session(self.test_session)

    def test_clear_session_success(self):
        """Test successfully clearing a session."""
        # Verify words exist
        pending = get_pending_words(self.test_session)
        self.assertEqual(len(pending), 7, "Should have 7 words before clearing")

        # Clear session
        removed = clear_session(self.test_session)

        # Should remove 7 words
        self.assertEqual(removed, 7, "Should remove 7 words")

        # Session should be empty
        pending_after = get_pending_words(self.test_session)
        self.assertEqual(len(pending_after), 0, "Session should be empty after clearing")

    def test_clear_empty_session(self):
        """Test clearing an empty session."""
        removed = clear_session("empty_session_xyz")

        # Should remove 0 words
        self.assertEqual(removed, 0, "Should remove 0 words from empty session")

    def test_clear_session_idempotent(self):
        """Test that clearing a session twice is safe (idempotent operation)."""
        # First clear
        removed1 = clear_session(self.test_session)
        self.assertGreater(removed1, 0, "First clear should remove words")

        # Second clear should be safe and remove nothing
        removed2 = clear_session(self.test_session)
        self.assertEqual(removed2, 0, "Second clear should remove 0 words")

        # Third clear should also be safe
        removed3 = clear_session(self.test_session)
        self.assertEqual(removed3, 0, "Third clear should remove 0 words")


class TestConcurrentSessions(unittest.TestCase):
    """Test concurrent session handling and isolation."""

    def setUp(self):
        """Set up test environment with concurrent sessions."""
        self.session_a = f"concurrent_a_{uuid.uuid4().hex[:8]}"
        self.session_b = f"concurrent_b_{uuid.uuid4().hex[:8]}"
        self.session_c = f"concurrent_c_{uuid.uuid4().hex[:8]}"

        # Add words to different sessions
        add_temp_word("word_a1", "word_a1", "NOUN", "trans_a1", True, self.session_a)
        add_temp_word("word_a2", "word_a2", "VERB", "trans_a2", False, self.session_a)

        add_temp_word("word_b1", "word_b1", "ADJ", "trans_b1", True, self.session_b)
        add_temp_word("word_b2", "word_b2", "NOUN", "trans_b2", True, self.session_b)
        add_temp_word("word_b3", "word_b3", "VERB", "trans_b3", False, self.session_b)

        add_temp_word("word_c1", "word_c1", "ADJ", "trans_c1", True, self.session_c)

    def tearDown(self):
        """Clean up test data."""
        clear_session(self.session_a)
        clear_session(self.session_b)
        clear_session(self.session_c)

    def test_session_isolation(self):
        """Test that sessions are properly isolated from each other."""
        # Get words from each session
        words_a = get_pending_words(self.session_a)
        words_b = get_pending_words(self.session_b)
        words_c = get_pending_words(self.session_c)

        # Check correct counts
        self.assertEqual(len(words_a), 2, "Session A should have 2 words")
        self.assertEqual(len(words_b), 3, "Session B should have 3 words")
        self.assertEqual(len(words_c), 1, "Session C should have 1 word")

        # Check session isolation
        lemmas_a = [word[1] for word in words_a]
        lemmas_b = [word[1] for word in words_b]
        lemmas_c = [word[1] for word in words_c]

        # Session A should only contain its words
        self.assertIn("word_a1", lemmas_a, "Session A should contain word_a1")
        self.assertIn("word_a2", lemmas_a, "Session A should contain word_a2")
        self.assertNotIn("word_b1", lemmas_a, "Session A should not contain words from B")
        self.assertNotIn("word_c1", lemmas_a, "Session A should not contain words from C")

        # Session B should only contain its words
        self.assertIn("word_b1", lemmas_b, "Session B should contain word_b1")
        self.assertNotIn("word_a1", lemmas_b, "Session B should not contain words from A")
        self.assertNotIn("word_c1", lemmas_b, "Session B should not contain words from C")

    def test_concurrent_operations(self):
        """Test concurrent operations on different sessions."""
        # Approve a word from session A
        approve_result = approve_word("word_a1", self.session_a)
        self.assertTrue(approve_result, "Approval in session A should succeed")

        # Reject a word from session B
        reject_result = reject_word("word_b2", self.session_b)
        self.assertTrue(reject_result, "Rejection in session B should succeed")

        # Clear session C
        clear_result = clear_session(self.session_c)
        self.assertEqual(clear_result, 1, "Clear session C should remove 1 word")

        # Verify session A still has 1 word (word_a2)
        words_a = get_pending_words(self.session_a)
        self.assertEqual(len(words_a), 1, "Session A should have 1 remaining word")

        # Verify session B still has 2 words (word_b1, word_b3)
        words_b = get_pending_words(self.session_b)
        self.assertEqual(len(words_b), 2, "Session B should have 2 remaining words")

        # Verify session C is empty
        words_c = get_pending_words(self.session_c)
        self.assertEqual(len(words_c), 0, "Session C should be empty")

        # Clean up approved word from main database
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE word = ?", ("word_a1",))
                conn.commit()
        except sqlite3.Error:
            pass


class TestDatabaseIntegrity(unittest.TestCase):
    """Test database integrity during transfer operations."""

    def setUp(self):
        """Set up test environment."""
        self.test_session = f"test_integrity_{uuid.uuid4().hex[:8]}"

        # Clean up any existing test words from main database
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE word LIKE 'integrity_test%'")
                conn.commit()
        except sqlite3.Error:
            pass

    def tearDown(self):
        """Clean up test data."""
        clear_session(self.test_session)

        # Clean up test words from main database
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE word LIKE 'integrity_test%'")
                conn.commit()
        except sqlite3.Error:
            pass

    def test_data_integrity_during_approval(self):
        """Test that all word data is correctly transferred during approval."""
        # Add word with specific data
        add_temp_word("integrity_test1", "integrity_test1", "NOUN", "test translation", True, self.test_session)

        # Approve word
        approve_word("integrity_test1", self.test_session)

        # Verify data integrity in main database
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT word, pos, is_regular, translation FROM {TABLE_NAME} WHERE word = ?",
                           ("integrity_test1",))
            result = cursor.fetchone()

        self.assertIsNotNone(result, "Word should exist in main database")
        self.assertEqual(result[0], "integrity_test1", "Word field should match")
        self.assertEqual(result[1], "NOUN", "POS field should match")
        self.assertEqual(result[2], 1, "is_regular field should match (SQLite stores as 1)")
        self.assertEqual(result[3], "test translation", "Translation field should match")

    def test_tag_integrity_during_approval(self):
        """Test that tags are correctly assigned during approval."""
        # Add word
        add_temp_word("integrity_test2", "integrity_test2", "VERB", "test2 translation", False, self.test_session)

        # Approve with tags
        tags = ["test-integrity-tag1", "test-integrity-tag2"]
        approve_word("integrity_test2", self.test_session, tags=tags)

        # Verify tags in database
        word_tags = get_word_tags("integrity_test2")
        tag_names = [tag[0] for tag in word_tags]

        self.assertEqual(len(tag_names), 2, "Should have 2 tags")
        self.assertIn("test-integrity-tag1", tag_names, "Tag 1 should be assigned")
        self.assertIn("test-integrity-tag2", tag_names, "Tag 2 should be assigned")

    def test_no_data_loss_on_rejection(self):
        """Test that rejection properly removes word without affecting other words."""
        # Add multiple words
        add_temp_word("integrity_test3", "integrity_test3", "NOUN", "test3", True, self.test_session)
        add_temp_word("integrity_test4", "integrity_test4", "ADJ", "test4", True, self.test_session)

        # Reject one word
        reject_word("integrity_test3", self.test_session)

        # Verify other word is unaffected
        pending = get_pending_words(self.test_session)
        self.assertEqual(len(pending), 1, "Should have 1 remaining word")

        lemmas = [word[1] for word in pending]
        self.assertNotIn("integrity_test3", lemmas, "Rejected word should be removed")
        self.assertIn("integrity_test4", lemmas, "Other word should remain")

    def test_cleanup_after_approval(self):
        """Test that temporary data is properly cleaned up after approval."""
        # Add word
        add_temp_word("integrity_test5", "integrity_test5", "VERB", "test5", False, self.test_session)

        # Verify word exists in temp
        self.assertTrue(temp_word_exists("integrity_test5", self.test_session),
                        "Word should exist in temp before approval")

        # Approve word
        approve_word("integrity_test5", self.test_session)

        # Verify word is removed from temp
        self.assertFalse(temp_word_exists("integrity_test5", self.test_session),
                         "Word should be removed from temp after approval")

        # Verify word exists in main database
        self.assertTrue(word_exists("integrity_test5"),
                        "Word should exist in main database after approval")


class TestErrorHandling(unittest.TestCase):
    """Test error handling for invalid operations."""

    def setUp(self):
        """Set up test environment."""
        self.test_session = f"test_error_{uuid.uuid4().hex[:8]}"

    def tearDown(self):
        """Clean up test data."""
        clear_session(self.test_session)

    def test_approve_with_empty_session_id(self):
        """Test error handling when approving with empty session ID."""
        add_temp_word("errortest1", "errortest1", "NOUN", "test", True, self.test_session)

        # Try to approve with empty session ID
        result = approve_word("errortest1", "")

        # Should fail gracefully
        self.assertFalse(result, "Should fail gracefully with empty session ID")

    def test_reject_with_empty_lemma(self):
        """Test error handling when rejecting with empty lemma."""
        # Try to reject with empty lemma
        result = reject_word("", self.test_session)

        # Should fail gracefully
        self.assertFalse(result, "Should fail gracefully with empty lemma")

    def test_database_error_handling(self):
        """Test that database operations handle errors gracefully."""
        # Try to approve a word that doesn't exist
        result = approve_word("nonexistent_word_xyz", self.test_session)

        # Should return False, not raise exception
        self.assertFalse(result, "Should return False for non-existent word")

    def test_operations_on_nonexistent_session(self):
        """Test operations on non-existent sessions fail gracefully."""
        fake_session = "nonexistent_session_xyz123"

        # All operations should fail gracefully
        approve_result = approve_word("anything", fake_session)
        reject_result = reject_word("anything", fake_session)
        clear_result = clear_session(fake_session)

        self.assertFalse(approve_result, "Approve should fail for non-existent session")
        self.assertFalse(reject_result, "Reject should fail for non-existent session")
        self.assertEqual(clear_result, 0, "Clear should return 0 for non-existent session")


def run_all_tests():
    """Run all test suites."""
    # Create test suite
    test_suite = unittest.TestSuite()

    # Add all test classes
    test_classes = [
        TestApproveWordOperations,
        TestRejectWordOperations,
        TestGetPendingWords,
        TestClearSession,
        TestConcurrentSessions,
        TestDatabaseIntegrity,
        TestErrorHandling
    ]

    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    print("=" * 80)
    print("COMPREHENSIVE TEMPORARY DATABASE OPERATIONS TEST SUITE (Issue #8)")
    print("=" * 80)
    print("\nTesting:")
    print("  - approve_word() with and without tags")
    print("  - reject_word() functionality")
    print("  - get_pending_words() with session filtering")
    print("  - clear_session() functionality")
    print("  - Error handling for invalid operations")
    print("  - Database integrity during transfer operations")
    print("  - Concurrent session handling")
    print()

    success = run_all_tests()

    if success:
        print("\n" + "=" * 80)
        print("[SUCCESS] ALL TEMPORARY DATABASE OPERATION TESTS PASSED!")
        print("=" * 80)
        print("\n[PASS] All acceptance criteria met:")
        print("  [PASS] All temporary database operations have corresponding tests")
        print("  [PASS] Tests verify correct data transfer from temporary to main database")
        print("  [PASS] Tests ensure proper cleanup of temporary data")
        print("  [PASS] Error scenarios are covered")
        print("  [PASS] Session management is thoroughly tested")
        print("  [PASS] Tests verify tag assignment during approval process")
        sys.exit(0)
    else:
        print("\n" + "=" * 80)
        print("[FAIL] SOME TESTS FAILED!")
        print("=" * 80)
        sys.exit(1)
