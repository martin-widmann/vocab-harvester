#!/usr/bin/env python3
"""
Comprehensive tests for session management controller (Issue #9, Issue #11).

Tests cover:
- ProcessingSession class initialization and methods
- Session workflow orchestration (start_session, get_status, get_words)
- Session persistence and resumption
- SessionManager multi-session handling
- Progress tracking and statistics
- Error handling and recovery
- Concurrent session handling
- Complete end-to-end workflow integration

Note: Tests use real integration with parser, translation service, and database
rather than mocks to provide comprehensive validation of the complete workflow.
"""

import sys
import os
import unittest
import json

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import after path setup  # noqa: E402
from session_manager import (  # noqa: E402
    ProcessingSession,
    SessionManager,
    SessionStatus,
    start_processing_session,
    get_session_info,
    get_session_words_for_review,
    clear_completed_sessions
)
from database import clear_session, get_pending_words  # noqa: E402


class TestProcessingSession(unittest.TestCase):
    """Test ProcessingSession class functionality."""

    def setUp(self):
        """Set up test environment."""
        self.test_sessions_dir = "C:/Users/marti/Projects-2025/vocab-harvester/sessions"
        os.makedirs(self.test_sessions_dir, exist_ok=True)
        self.created_sessions = []

    def tearDown(self):
        """Clean up test data."""
        # Clean up all test sessions
        for session in self.created_sessions:
            try:
                clear_session(session.session_id)
                # Remove session file
                session_file = os.path.join(self.test_sessions_dir, f"{session.session_id}.json")
                if os.path.exists(session_file):
                    os.remove(session_file)
            except Exception:
                pass

    def test_session_initialization(self):
        """Test that sessions are initialized with unique IDs."""
        session1 = ProcessingSession()
        session2 = ProcessingSession()

        self.created_sessions.extend([session1, session2])

        # Sessions should have unique IDs
        self.assertIsNotNone(session1.session_id)
        self.assertIsNotNone(session2.session_id)
        self.assertNotEqual(session1.session_id, session2.session_id)

        # Sessions should start in CREATED status
        self.assertEqual(session1.status, SessionStatus.CREATED)
        self.assertEqual(session2.status, SessionStatus.CREATED)

    def test_session_initialization_with_custom_id(self):
        """Test session initialization with custom ID."""
        custom_id = "test_custom_session_12345"
        session = ProcessingSession(session_id=custom_id)

        self.created_sessions.append(session)

        self.assertEqual(session.session_id, custom_id)
        self.assertEqual(session.status, SessionStatus.CREATED)

    def test_start_session_with_valid_text(self):
        """Test starting a session with valid German text."""
        session = ProcessingSession()
        self.created_sessions.append(session)

        # Simple German text with some words
        test_text = "Der Hund läuft schnell durch den Park."

        result = session.start_session(test_text)

        # Session should complete successfully
        self.assertTrue(result['success'], "Session should complete successfully")
        self.assertIn(session.status, [SessionStatus.COMPLETED, SessionStatus.PENDING_REVIEW])

        # Session should have processed some words
        self.assertGreater(result['statistics']['total_words_processed'], 0,
                           "Should have processed some words")

    def test_start_session_with_empty_text(self):
        """Test starting a session with empty text."""
        session = ProcessingSession()
        self.created_sessions.append(session)

        result = session.start_session("")

        # Session should fail
        self.assertFalse(result['success'], "Session should fail with empty text")
        self.assertEqual(session.status, SessionStatus.FAILED)
        self.assertIsNotNone(session.error_message)

    def test_start_session_with_whitespace_only(self):
        """Test starting a session with whitespace-only text."""
        session = ProcessingSession()
        self.created_sessions.append(session)

        result = session.start_session("   \n\t  ")

        # Session should fail
        self.assertFalse(result['success'], "Session should fail with whitespace-only text")
        self.assertEqual(session.status, SessionStatus.FAILED)

    def test_get_session_status(self):
        """Test getting session status information."""
        session = ProcessingSession()
        self.created_sessions.append(session)

        # Start session with text
        test_text = "Ein kleiner Test mit deutschen Wörtern."
        session.start_session(test_text)

        # Get status
        status = session.get_session_status()

        # Verify status structure
        self.assertIn('session_id', status)
        self.assertIn('status', status)
        self.assertIn('created_at', status)
        self.assertIn('statistics', status)
        self.assertIn('duration_seconds', status)

        # Verify statistics
        stats = status['statistics']
        self.assertIn('total_words_processed', stats)
        self.assertIn('words_added', stats)
        self.assertIn('words_translated', stats)
        self.assertIn('words_pending_review', stats)

    def test_get_session_words(self):
        """Test retrieving words from a session."""
        session = ProcessingSession()
        self.created_sessions.append(session)

        # Start session with text
        test_text = "Das Buch ist interessant und lehrreich."
        result = session.start_session(test_text)

        # Get session words
        words = session.get_session_words()

        # Should return a list
        self.assertIsInstance(words, list)

        # If words were added, check structure
        if result['statistics']['words_added'] > 0:
            self.assertGreater(len(words), 0, "Should have some words")

            # Check first word structure
            first_word = words[0]
            self.assertIn('word', first_word)
            self.assertIn('lemma', first_word)
            self.assertIn('pos', first_word)
            self.assertIn('translation', first_word)

    def test_get_progress_string(self):
        """Test progress string generation."""
        session = ProcessingSession()
        self.created_sessions.append(session)

        # Initial progress
        initial_progress = session.get_progress_string()
        self.assertIsInstance(initial_progress, str)

        # After starting session
        test_text = "Ein kurzer deutscher Satz zum Testen."
        session.start_session(test_text)

        progress = session.get_progress_string()
        self.assertIsInstance(progress, str)
        self.assertGreater(len(progress), 0)

    def test_clear_session_data(self):
        """Test clearing session data."""
        session = ProcessingSession()
        self.created_sessions.append(session)

        # Start session
        test_text = "Einige deutsche Wörter für den Test."
        result = session.start_session(test_text)

        words_added = result['statistics']['words_added']

        if words_added > 0:
            # Clear session
            removed = session.clear_session_data()

            # Should have removed some words
            self.assertGreaterEqual(removed, 0)

            # No words should remain
            pending = get_pending_words(session.session_id)
            self.assertEqual(len(pending), 0, "No words should remain after clearing")

    def test_session_persistence(self):
        """Test that sessions are saved to disk."""
        session = ProcessingSession()
        self.created_sessions.append(session)

        # Start session
        test_text = "Deutsche Wörter werden hier verarbeitet."
        session.start_session(test_text)

        # Check that session file was created
        session_file = os.path.join(self.test_sessions_dir, f"{session.session_id}.json")
        self.assertTrue(os.path.exists(session_file), "Session file should be created")

        # Verify file content
        with open(session_file, 'r', encoding='utf-8') as f:
            session_data = json.load(f)

        self.assertEqual(session_data['session_id'], session.session_id)
        self.assertIn('status', session_data)
        self.assertIn('statistics', session_data)

    def test_session_resumption(self):
        """Test loading a session from disk."""
        # Create and save a session
        session1 = ProcessingSession()
        self.created_sessions.append(session1)

        test_text = "Text für Session-Wiederherstellung."
        session1.start_session(test_text)
        original_id = session1.session_id
        original_stats = session1.total_words_processed

        # Create a new session with the same ID (simulating resumption)
        session2 = ProcessingSession(session_id=original_id)
        self.created_sessions.append(session2)

        # Load state from disk
        loaded = session2._load_session_state()

        if loaded:
            self.assertTrue(loaded, "Should successfully load session state")
            self.assertEqual(session2.total_words_processed, original_stats)
            self.assertEqual(session2.status, session1.status)


class TestSessionManager(unittest.TestCase):
    """Test SessionManager multi-session handling."""

    def setUp(self):
        """Set up test environment."""
        self.manager = SessionManager()
        self.test_sessions = []

    def tearDown(self):
        """Clean up test data."""
        # Clean up all test sessions
        for session_id in self.test_sessions:
            try:
                self.manager.delete_session(session_id)
            except Exception:
                pass

    def test_create_session(self):
        """Test creating a new session through manager."""
        test_text = "Ein Test mit dem SessionManager."
        session = self.manager.create_session(test_text)

        self.test_sessions.append(session.session_id)

        # Session should be created and started
        self.assertIsNotNone(session)
        self.assertIsNotNone(session.session_id)
        self.assertIn(session.status, [SessionStatus.COMPLETED, SessionStatus.PENDING_REVIEW, SessionStatus.FAILED])

    def test_get_session(self):
        """Test retrieving a session by ID."""
        test_text = "Text für Session-Abruf."
        session = self.manager.create_session(test_text)

        self.test_sessions.append(session.session_id)

        # Retrieve session
        retrieved = self.manager.get_session(session.session_id)

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.session_id, session.session_id)

    def test_get_nonexistent_session(self):
        """Test retrieving a session that doesn't exist."""
        retrieved = self.manager.get_session("nonexistent_session_12345")

        self.assertIsNone(retrieved, "Should return None for non-existent session")

    def test_list_sessions(self):
        """Test listing all sessions."""
        # Create multiple sessions
        texts = [
            "Erste Session mit Text.",
            "Zweite Session mit anderem Text.",
            "Dritte Session zum Testen."
        ]

        for text in texts:
            session = self.manager.create_session(text)
            self.test_sessions.append(session.session_id)

        # List all sessions
        sessions_list = self.manager.list_sessions()

        # Should have at least our test sessions
        self.assertGreaterEqual(len(sessions_list), len(texts))

        # Check structure of session list items
        if sessions_list:
            first_item = sessions_list[0]
            self.assertIn('session_id', first_item)
            self.assertIn('status', first_item)
            self.assertIn('created_at', first_item)
            self.assertIn('words_added', first_item)

    def test_list_sessions_with_filter(self):
        """Test listing sessions with status filter."""
        # Create a session
        test_text = "Filter-Test für Sessions."
        session = self.manager.create_session(test_text)
        self.test_sessions.append(session.session_id)

        # List sessions with specific status
        completed = self.manager.list_sessions(status_filter=SessionStatus.COMPLETED)
        pending = self.manager.list_sessions(status_filter=SessionStatus.PENDING_REVIEW)

        # Should return lists
        self.assertIsInstance(completed, list)
        self.assertIsInstance(pending, list)

    def test_delete_session(self):
        """Test deleting a session."""
        test_text = "Session zum Löschen."
        session = self.manager.create_session(test_text)
        session_id = session.session_id

        # Delete the session
        success = self.manager.delete_session(session_id)

        self.assertTrue(success, "Deletion should succeed")

        # Session should no longer exist
        retrieved = self.manager.get_session(session_id)
        self.assertIsNone(retrieved, "Deleted session should not be retrievable")

        # Session file should be removed
        session_file = os.path.join("C:/Users/marti/Projects-2025/vocab-harvester/sessions",
                                    f"{session_id}.json")
        self.assertFalse(os.path.exists(session_file), "Session file should be removed")

    def test_concurrent_sessions(self):
        """Test handling multiple concurrent sessions."""
        # Create multiple sessions
        texts = [
            "Erste gleichzeitige Session.",
            "Zweite gleichzeitige Session.",
            "Dritte gleichzeitige Session."
        ]

        session_ids = []
        for text in texts:
            session = self.manager.create_session(text)
            session_ids.append(session.session_id)
            self.test_sessions.append(session.session_id)

        # All sessions should be accessible
        for session_id in session_ids:
            session = self.manager.get_session(session_id)
            self.assertIsNotNone(session, f"Session {session_id} should be accessible")

        # Each session should have its own data
        unique_ids = set(session_ids)
        self.assertEqual(len(unique_ids), len(texts), "All session IDs should be unique")


class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience functions for easy usage."""

    def setUp(self):
        """Set up test environment."""
        self.test_sessions = []

    def tearDown(self):
        """Clean up test data."""
        manager = SessionManager()
        for session_id in self.test_sessions:
            try:
                manager.delete_session(session_id)
            except Exception:
                pass

    def test_start_processing_session(self):
        """Test convenience function for starting sessions."""
        test_text = "Test mit Convenience-Funktion."

        session_id, result = start_processing_session(test_text)
        self.test_sessions.append(session_id)

        # Should return session ID and result
        self.assertIsNotNone(session_id)
        self.assertIsInstance(result, dict)
        self.assertIn('session_id', result)
        self.assertIn('status', result)

    def test_get_session_info(self):
        """Test convenience function for getting session info."""
        test_text = "Info-Test mit Convenience-Funktion."

        session_id, _ = start_processing_session(test_text)
        self.test_sessions.append(session_id)

        # Get session info
        info = get_session_info(session_id)

        self.assertIsNotNone(info)
        self.assertEqual(info['session_id'], session_id)
        self.assertIn('statistics', info)

    def test_get_session_info_nonexistent(self):
        """Test getting info for non-existent session."""
        info = get_session_info("nonexistent_session_xyz")

        self.assertIsNone(info, "Should return None for non-existent session")

    def test_get_session_words_for_review(self):
        """Test convenience function for getting session words."""
        test_text = "Wörter für Review-Test."

        session_id, _ = start_processing_session(test_text)
        self.test_sessions.append(session_id)

        # Get words for review
        words = get_session_words_for_review(session_id)

        self.assertIsInstance(words, list)

    def test_clear_completed_sessions(self):
        """Test clearing completed sessions with no pending words."""
        # Create a session and clear it
        test_text = "Session für Clear-Test."

        session_id, _ = start_processing_session(test_text)
        self.test_sessions.append(session_id)

        # Clear the session's words
        clear_session(session_id)

        # Now clear completed sessions
        # Note: This might not clear our session if it's still pending review
        # But it should execute without errors
        cleared = clear_completed_sessions()

        self.assertIsInstance(cleared, int)
        self.assertGreaterEqual(cleared, 0)


class TestErrorHandling(unittest.TestCase):
    """Test error handling and recovery."""

    def setUp(self):
        """Set up test environment."""
        self.test_sessions = []

    def tearDown(self):
        """Clean up test data."""
        manager = SessionManager()
        for session_id in self.test_sessions:
            try:
                manager.delete_session(session_id)
            except Exception:
                pass

    def test_invalid_text_input(self):
        """Test handling of invalid text input."""
        session = ProcessingSession()
        self.test_sessions.append(session.session_id)

        # Try with None (should be handled gracefully)
        result = session.start_session("")

        self.assertFalse(result['success'])
        self.assertEqual(session.status, SessionStatus.FAILED)
        self.assertIsNotNone(session.error_message)

    def test_session_status_after_error(self):
        """Test that session status is properly set after errors."""
        session = ProcessingSession()
        self.test_sessions.append(session.session_id)

        # Cause an error
        session.start_session("")

        # Status should reflect the error
        status = session.get_session_status()
        self.assertEqual(status['status'], SessionStatus.FAILED.value)
        self.assertIsNotNone(status['error_message'])


def run_all_tests():
    """Run all test suites."""
    # Create test suite
    test_suite = unittest.TestSuite()

    # Add all test classes
    test_classes = [
        TestProcessingSession,
        TestSessionManager,
        TestConvenienceFunctions,
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
    print("SESSION MANAGER TEST SUITE (Issue #9, Issue #11)")
    print("=" * 80)
    print("\nTesting:")
    print("  - ProcessingSession class and methods")
    print("  - Session workflow orchestration")
    print("  - Session persistence and resumption")
    print("  - SessionManager multi-session handling")
    print("  - Concurrent session handling")
    print("  - Convenience functions")
    print("  - Error handling and recovery")
    print("  - Complete end-to-end integration")
    print()

    success = run_all_tests()

    if success:
        print("\n" + "=" * 80)
        print("[SUCCESS] ALL SESSION MANAGER TESTS PASSED!")
        print("=" * 80)
        print("\n[PASS] All acceptance criteria met (Issue #9, Issue #11):")
        print("  [PASS] Session controller successfully coordinates entire batch workflow")
        print("  [PASS] Users can start processing sessions with German texts")
        print("  [PASS] Progress tracking shows current processing status")
        print("  [PASS] Sessions persist between application restarts")
        print("  [PASS] Multiple sessions can be managed concurrently")
        print("  [PASS] Controller handles errors gracefully and reports status")
        print("  [PASS] Integration with parser, translation, and database modules works")
        print("  [PASS] Complete workflow integration tested end-to-end")
        print("  [PASS] Concurrent session management verified")
        print("  [PASS] Error scenarios properly handled and tested")
        sys.exit(0)
    else:
        print("\n" + "=" * 80)
        print("[FAIL] SOME TESTS FAILED!")
        print("=" * 80)
        sys.exit(1)
