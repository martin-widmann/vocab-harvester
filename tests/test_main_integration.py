#!/usr/bin/env python3
"""
Integration tests for main.py entry point (Issue #10).

Tests cover:
- Import validation
- Session management integration
- Database function availability
- Review interface integration
"""

import sys
import os
import unittest

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestMainIntegration(unittest.TestCase):
    """Test main.py integration with session management controller."""

    def test_imports(self):
        """Test that all required imports are available."""
        try:
            # Import main module components
            from session_manager import (  # noqa: F401
                SessionManager,
                SessionStatus,
                start_processing_session,
                get_session_info
            )
            from database import (  # noqa: F401
                get_pending_words,
                approve_word,
                reject_word
            )
            from review import review_interface  # noqa: F401

            # If we get here, all imports are successful
            self.assertTrue(True, "All imports successful")

        except ImportError as e:
            self.fail(f"Import failed: {e}")

    def test_session_manager_initialization(self):
        """Test that SessionManager can be initialized."""
        from session_manager import SessionManager

        manager = SessionManager()
        self.assertIsNotNone(manager)
        self.assertIsInstance(manager.sessions, dict)

    def test_session_status_enum(self):
        """Test that SessionStatus enum is available and has required values."""
        from session_manager import SessionStatus

        # Check all required status values exist
        required_statuses = ['CREATED', 'PROCESSING', 'COMPLETED', 'FAILED', 'PENDING_REVIEW']

        for status_name in required_statuses:
            self.assertTrue(hasattr(SessionStatus, status_name),
                            f"SessionStatus should have {status_name}")

    def test_start_processing_session_function(self):
        """Test that start_processing_session function works."""
        from session_manager import start_processing_session, SessionManager

        test_text = "Ein einfacher Test für die Integration."

        try:
            session_id, result = start_processing_session(test_text)

            # Clean up
            manager = SessionManager()
            manager.delete_session(session_id)

            # Verify result structure
            self.assertIsNotNone(session_id)
            self.assertIsInstance(result, dict)
            self.assertIn('session_id', result)
            self.assertIn('status', result)
            self.assertIn('statistics', result)

        except Exception as e:
            self.fail(f"start_processing_session failed: {e}")

    def test_get_session_info_function(self):
        """Test that get_session_info function works."""
        from session_manager import start_processing_session, get_session_info, SessionManager

        test_text = "Test für get_session_info Funktion."

        try:
            session_id, _ = start_processing_session(test_text)

            # Get session info
            info = get_session_info(session_id)

            # Clean up
            manager = SessionManager()
            manager.delete_session(session_id)

            # Verify info structure
            self.assertIsNotNone(info)
            self.assertEqual(info['session_id'], session_id)
            self.assertIn('statistics', info)
            self.assertIn('status', info)

        except Exception as e:
            self.fail(f"get_session_info failed: {e}")

    def test_database_functions_available(self):
        """Test that database functions used in main.py are available."""
        from database import get_pending_words, approve_word, reject_word

        # Test that functions are callable
        self.assertTrue(callable(get_pending_words))
        self.assertTrue(callable(approve_word))
        self.assertTrue(callable(reject_word))

    def test_review_interface_available(self):
        """Test that review_interface is available."""
        from review import review_interface

        self.assertTrue(callable(review_interface))

    def test_display_session_summary_logic(self):
        """Test that session summary display logic works with real data."""
        from session_manager import start_processing_session, get_session_info, SessionManager

        test_text = "Testtext für Session-Zusammenfassung."

        try:
            session_id, _ = start_processing_session(test_text)

            # Get session info
            session_info = get_session_info(session_id)

            # Clean up
            manager = SessionManager()
            manager.delete_session(session_id)

            # Verify all required keys for display_session_summary
            required_keys = ['session_id', 'status', 'duration_seconds', 'statistics',
                             'error_message', 'text_preview']

            for key in required_keys:
                self.assertIn(key, session_info, f"session_info should have key '{key}'")

            # Verify statistics structure
            stats = session_info['statistics']
            required_stats = ['total_words_processed', 'words_added', 'words_translated',
                              'words_pending_review']

            for stat in required_stats:
                self.assertIn(stat, stats, f"statistics should have key '{stat}'")

        except Exception as e:
            self.fail(f"Session summary logic failed: {e}")

    def test_session_manager_list_sessions(self):
        """Test that SessionManager.list_sessions works as expected in main.py."""
        from session_manager import SessionManager, SessionStatus

        manager = SessionManager()

        # Test listing all sessions
        try:
            all_sessions = manager.list_sessions()
            self.assertIsInstance(all_sessions, list)

            # Test listing with status filter
            pending_sessions = manager.list_sessions(status_filter=SessionStatus.PENDING_REVIEW)
            self.assertIsInstance(pending_sessions, list)

        except Exception as e:
            self.fail(f"list_sessions failed: {e}")

    def test_pending_words_function(self):
        """Test that get_pending_words works correctly."""
        from database import get_pending_words

        try:
            # Test with no session_id (should return all pending words)
            all_pending = get_pending_words()
            self.assertIsInstance(all_pending, list)

            # Test with specific session_id
            specific_pending = get_pending_words("nonexistent_session")
            self.assertIsInstance(specific_pending, list)
            self.assertEqual(len(specific_pending), 0,
                             "Should return empty list for nonexistent session")

        except Exception as e:
            self.fail(f"get_pending_words failed: {e}")


def run_integration_tests():
    """Run all integration tests."""
    # Create test suite
    test_suite = unittest.TestLoader().loadTestsFromTestCase(TestMainIntegration)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    print("=" * 80)
    print("MAIN.PY INTEGRATION TEST SUITE (Issue #10)")
    print("=" * 80)
    print("\nTesting:")
    print("  - Import validation for main.py dependencies")
    print("  - Session management integration")
    print("  - Database function availability")
    print("  - Review interface integration")
    print()

    success = run_integration_tests()

    if success:
        print("\n" + "=" * 80)
        print("[SUCCESS] ALL MAIN.PY INTEGRATION TESTS PASSED!")
        print("=" * 80)
        print("\n[PASS] All integration requirements met:")
        print("  [PASS] All imports work correctly")
        print("  [PASS] Session management controller integrates properly")
        print("  [PASS] Database functions are accessible")
        print("  [PASS] Review interface is available")
        print("  [PASS] Session summary display works with real data")
        sys.exit(0)
    else:
        print("\n" + "=" * 80)
        print("[FAIL] SOME INTEGRATION TESTS FAILED!")
        print("=" * 80)
        sys.exit(1)
