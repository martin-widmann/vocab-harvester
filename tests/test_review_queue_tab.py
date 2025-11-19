"""Test the Review Queue tab UI."""

import sys
import os
import tkinter as tk
from unittest.mock import patch, MagicMock

# Add src/ui to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'ui'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tabs.review_queue_tab import ReviewQueueTab


class TestReviewQueueTabUI:
    """Test Review Queue tab UI elements."""

    def setup_method(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.tab = ReviewQueueTab(self.root)
        self.root.update_idletasks()

    def teardown_method(self):
        """Clean up after tests."""
        self.root.destroy()

    def test_tab_initialization(self):
        """Test that tab initializes correctly."""
        assert self.tab is not None
        assert self.tab._current_session_id is None
        assert self.tab._words == []
        assert self.tab._current_index == 0

    def test_difficulty_default_value(self):
        """Test that difficulty defaults to 3 (Medium)."""
        assert self.tab._difficulty.get() == 3

    def test_session_combo_exists(self):
        """Test that session combobox exists."""
        assert hasattr(self.tab, 'session_combo')
        assert self.tab.session_combo is not None

    def test_load_button_exists(self):
        """Test that load button exists."""
        assert hasattr(self.tab, 'load_button')

    def test_action_buttons_exist(self):
        """Test that all action buttons exist."""
        assert hasattr(self.tab, 'approve_button')
        assert hasattr(self.tab, 'reject_button')
        assert hasattr(self.tab, 'skip_button')

    def test_action_buttons_initially_disabled(self):
        """Test that action buttons are disabled when no session loaded."""
        assert 'disabled' in str(self.tab.approve_button['state'])
        assert 'disabled' in str(self.tab.reject_button['state'])
        assert 'disabled' in str(self.tab.skip_button['state'])

    def test_word_labels_exist(self):
        """Test that all word display labels exist."""
        assert hasattr(self.tab, 'original_label')
        assert hasattr(self.tab, 'lemma_label')
        assert hasattr(self.tab, 'pos_label')
        assert hasattr(self.tab, 'translation_label')

    def test_progress_label_exists(self):
        """Test that progress label exists."""
        assert hasattr(self.tab, 'progress_label')
        assert 'No session loaded' in self.tab.progress_label.cget('text')

    def test_tags_entry_exists(self):
        """Test that tags entry field exists."""
        assert hasattr(self.tab, 'tags_entry')


class TestReviewQueueTabState:
    """Test Review Queue tab state management."""

    def setup_method(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.tab = ReviewQueueTab(self.root)
        self.root.update_idletasks()

    def teardown_method(self):
        """Clean up after tests."""
        self.root.destroy()

    def test_update_button_states_enabled(self):
        """Test that buttons are enabled when words are loaded."""
        # Simulate loaded words
        self.tab._words = [('test', 'test', 'NOUN', 'test', True, 'session1', '2024-01-01')]
        self.tab._current_index = 0

        self.tab._update_button_states()

        assert str(self.tab.approve_button['state']) in ['normal', 'enabled', '!disabled']
        assert str(self.tab.reject_button['state']) in ['normal', 'enabled', '!disabled']
        assert str(self.tab.skip_button['state']) in ['normal', 'enabled', '!disabled']

    def test_update_button_states_disabled_when_past_end(self):
        """Test that buttons are disabled when index exceeds words."""
        self.tab._words = [('test', 'test', 'NOUN', 'test', True, 'session1', '2024-01-01')]
        self.tab._current_index = 1  # Past the end

        self.tab._update_button_states()

        assert 'disabled' in str(self.tab.approve_button['state'])

    def test_get_tags_empty(self):
        """Test that empty tags return None."""
        self.tab.tags_entry.delete(0, 'end')
        assert self.tab._get_tags() is None

    def test_get_tags_single(self):
        """Test parsing single tag."""
        self.tab.tags_entry.delete(0, 'end')
        self.tab.tags_entry.insert(0, 'medical')
        tags = self.tab._get_tags()
        assert tags == ['medical']

    def test_get_tags_multiple(self):
        """Test parsing multiple tags."""
        self.tab.tags_entry.delete(0, 'end')
        self.tab.tags_entry.insert(0, 'medical, difficult, technical')
        tags = self.tab._get_tags()
        assert tags == ['medical', 'difficult', 'technical']

    def test_get_tags_with_whitespace(self):
        """Test that tags are trimmed."""
        self.tab.tags_entry.delete(0, 'end')
        self.tab.tags_entry.insert(0, '  medical  ,  difficult  ')
        tags = self.tab._get_tags()
        assert tags == ['medical', 'difficult']

    def test_get_tags_empty_strings_removed(self):
        """Test that empty strings are removed from tags."""
        self.tab.tags_entry.delete(0, 'end')
        self.tab.tags_entry.insert(0, 'medical,,difficult,')
        tags = self.tab._get_tags()
        assert tags == ['medical', 'difficult']


class TestReviewQueueTabBehavior:
    """Test Review Queue tab behavior."""

    def setup_method(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.tab = ReviewQueueTab(self.root)
        self.root.update_idletasks()

    def teardown_method(self):
        """Clean up after tests."""
        self.root.destroy()

    def test_display_current_word(self):
        """Test that word data is displayed correctly."""
        # Set up test word
        self.tab._words = [
            ('original', 'lemma', 'NOUN', 'translation', True, 'session1', '2024-01-01')
        ]
        self.tab._current_index = 0

        self.tab._display_current_word()

        assert self.tab.original_label.cget('text') == 'original'
        assert self.tab.lemma_label.cget('text') == 'lemma'
        assert self.tab.pos_label.cget('text') == 'NOUN'
        assert self.tab.translation_label.cget('text') == 'translation'

    def test_display_word_without_translation(self):
        """Test display when word has no translation."""
        self.tab._words = [
            ('original', 'lemma', 'VERB', None, True, 'session1', '2024-01-01')
        ]
        self.tab._current_index = 0

        self.tab._display_current_word()

        assert self.tab.translation_label.cget('text') == 'No translation'

    def test_update_progress(self):
        """Test progress label updates correctly."""
        self.tab._words = [
            ('word1', 'lemma1', 'NOUN', None, True, 's1', '2024-01-01'),
            ('word2', 'lemma2', 'VERB', None, True, 's1', '2024-01-01'),
            ('word3', 'lemma3', 'ADJ', None, True, 's1', '2024-01-01'),
        ]
        self.tab._current_index = 1

        self.tab._update_progress()

        assert 'Word 2 of 3' in self.tab.progress_label.cget('text')

    def test_skip_word_advances_index(self):
        """Test that skip advances to next word."""
        self.tab._words = [
            ('word1', 'lemma1', 'NOUN', None, True, 's1', '2024-01-01'),
            ('word2', 'lemma2', 'VERB', None, True, 's1', '2024-01-01'),
        ]
        self.tab._current_index = 0
        self.tab._current_session_id = 's1'

        self.tab._skip_word()

        assert self.tab._current_index == 1

    def test_difficulty_reset_on_new_word(self):
        """Test that difficulty resets to default on new word."""
        self.tab._words = [
            ('word1', 'lemma1', 'NOUN', None, True, 's1', '2024-01-01'),
        ]
        self.tab._current_index = 0
        self.tab._difficulty.set(1)  # Change from default

        self.tab._display_current_word()

        assert self.tab._difficulty.get() == 3  # Reset to default

    def test_tags_cleared_on_new_word(self):
        """Test that tags entry is cleared on new word."""
        self.tab._words = [
            ('word1', 'lemma1', 'NOUN', None, True, 's1', '2024-01-01'),
        ]
        self.tab._current_index = 0
        self.tab.tags_entry.insert(0, 'some tags')

        self.tab._display_current_word()

        assert self.tab.tags_entry.get() == ''

    @patch('tabs.review_queue_tab.get_all_sessions')
    def test_refresh_sessions_with_data(self, mock_get_sessions):
        """Test refreshing sessions populates the combobox."""
        mock_get_sessions.return_value = [
            ('session1', 5, '2024-01-01'),
            ('session2', 10, '2024-01-02'),
        ]

        self.tab._refresh_sessions()

        values = self.tab.session_combo['values']
        assert len(values) == 2
        assert 'session1' in values[0]
        assert '5 words' in values[0]

    @patch('tabs.review_queue_tab.get_all_sessions')
    @patch('tkinter.messagebox.showinfo')
    def test_refresh_sessions_empty(self, mock_info, mock_get_sessions):
        """Test refreshing sessions shows message when empty."""
        mock_get_sessions.return_value = []

        self.tab._refresh_sessions()

        mock_info.assert_called_once()
        assert 'No' in mock_info.call_args[0][0]

    @patch('tkinter.messagebox.showwarning')
    def test_load_session_no_selection(self, mock_warning):
        """Test loading session with no selection shows warning."""
        self.tab.session_combo.set('')

        self.tab._load_session()

        mock_warning.assert_called_once()

    @patch('tabs.review_queue_tab.approve_word')
    def test_approve_word_calls_backend(self, mock_approve):
        """Test that approve calls the backend function."""
        mock_approve.return_value = True

        self.tab._words = [
            ('original', 'lemma', 'NOUN', 'trans', True, 'session1', '2024-01-01')
        ]
        self.tab._current_index = 0
        self.tab._current_session_id = 'session1'
        self.tab._difficulty.set(2)

        self.tab._approve_word()

        mock_approve.assert_called_once_with('lemma', 'session1', 2, None)

    @patch('tabs.review_queue_tab.approve_word')
    def test_approve_word_with_tags(self, mock_approve):
        """Test that approve passes tags to backend."""
        mock_approve.return_value = True

        self.tab._words = [
            ('original', 'lemma', 'NOUN', 'trans', True, 'session1', '2024-01-01')
        ]
        self.tab._current_index = 0
        self.tab._current_session_id = 'session1'
        self.tab.tags_entry.insert(0, 'medical, technical')

        self.tab._approve_word()

        mock_approve.assert_called_once()
        call_args = mock_approve.call_args[0]
        assert call_args[3] == ['medical', 'technical']

    @patch('tabs.review_queue_tab.reject_word')
    def test_reject_word_calls_backend(self, mock_reject):
        """Test that reject calls the backend function."""
        mock_reject.return_value = True

        self.tab._words = [
            ('original', 'lemma', 'NOUN', 'trans', True, 'session1', '2024-01-01')
        ]
        self.tab._current_index = 0
        self.tab._current_session_id = 'session1'

        self.tab._reject_word()

        mock_reject.assert_called_once_with('lemma', 'session1')

    def test_session_complete_clears_state(self):
        """Test that session complete clears the state."""
        self.tab._words = [('test', 'test', 'NOUN', 'test', True, 's1', '2024-01-01')]
        self.tab._current_session_id = 's1'
        self.tab._current_index = 0

        self.tab._show_session_complete()

        assert self.tab._words == []
        assert self.tab._current_session_id is None
        assert 'Session complete' in self.tab.progress_label.cget('text')


class TestReviewQueueTabIntegration:
    """Test Review Queue tab integration scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.tab = ReviewQueueTab(self.root)
        self.root.update_idletasks()

    def teardown_method(self):
        """Clean up after tests."""
        self.root.destroy()

    @patch('tabs.review_queue_tab.approve_word')
    def test_approve_advances_to_next_word(self, mock_approve):
        """Test that approving advances to the next word."""
        mock_approve.return_value = True

        self.tab._words = [
            ('word1', 'lemma1', 'NOUN', 'trans1', True, 's1', '2024-01-01'),
            ('word2', 'lemma2', 'VERB', 'trans2', True, 's1', '2024-01-01'),
        ]
        self.tab._current_index = 0
        self.tab._current_session_id = 's1'

        self.tab._approve_word()

        assert self.tab._current_index == 1
        assert self.tab.lemma_label.cget('text') == 'lemma2'

    @patch('tabs.review_queue_tab.reject_word')
    def test_reject_advances_to_next_word(self, mock_reject):
        """Test that rejecting advances to the next word."""
        mock_reject.return_value = True

        self.tab._words = [
            ('word1', 'lemma1', 'NOUN', 'trans1', True, 's1', '2024-01-01'),
            ('word2', 'lemma2', 'VERB', 'trans2', True, 's1', '2024-01-01'),
        ]
        self.tab._current_index = 0
        self.tab._current_session_id = 's1'

        self.tab._reject_word()

        assert self.tab._current_index == 1

    @patch('tabs.review_queue_tab.approve_word')
    def test_approve_last_word_shows_complete(self, mock_approve):
        """Test that approving last word shows session complete."""
        mock_approve.return_value = True

        self.tab._words = [
            ('word1', 'lemma1', 'NOUN', 'trans1', True, 's1', '2024-01-01'),
        ]
        self.tab._current_index = 0
        self.tab._current_session_id = 's1'

        self.tab._approve_word()

        assert 'Session complete' in self.tab.progress_label.cget('text')


def run_tests():
    """Run all tests."""
    import pytest
    pytest.main([__file__, '-v'])


if __name__ == "__main__":
    run_tests()
