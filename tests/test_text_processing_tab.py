"""Test the Text Processing tab UI."""

import sys
import os
import tkinter as tk
from unittest.mock import patch, MagicMock

# Add src/ui to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'ui'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tabs.text_processing_tab import TextProcessingTab


class TestTextProcessingTabUI:
    """Test Text Processing tab UI elements."""

    def setup_method(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.notebook = tk.ttk.Notebook(self.root)
        self.tab = TextProcessingTab(self.notebook, notebook=self.notebook)
        self.root.update_idletasks()

    def teardown_method(self):
        """Clean up after tests."""
        self.root.destroy()

    def test_tab_initialization(self):
        """Test that tab initializes correctly."""
        assert self.tab is not None
        assert self.tab.notebook == self.notebook
        assert self.tab._is_processing is False

    def test_text_input_exists(self):
        """Test that text input widget exists."""
        assert hasattr(self.tab, 'text_input')
        assert self.tab.text_input is not None

    def test_placeholder_text_present(self):
        """Test that placeholder text is shown initially."""
        text = self.tab.text_input.get('1.0', 'end-1c')
        assert text == "Paste German text here..."

    def test_process_button_exists(self):
        """Test that process button exists and is enabled."""
        assert hasattr(self.tab, 'process_button')
        assert str(self.tab.process_button['state']) in ['normal', 'enabled', '!disabled']

    def test_clear_button_exists(self):
        """Test that clear button exists and is enabled."""
        assert hasattr(self.tab, 'clear_button')
        assert str(self.tab.clear_button['state']) in ['normal', 'enabled', '!disabled']

    def test_clear_text_removes_content(self):
        """Test that clear button removes text content."""
        # Add some text
        self.tab.text_input.delete('1.0', 'end')
        self.tab.text_input.insert('1.0', 'Some test text')

        # Click clear
        self.tab._clear_text()

        # Verify text is empty
        text = self.tab.text_input.get('1.0', 'end-1c')
        assert text == ""

    def test_results_frame_initially_hidden(self):
        """Test that results frame is not visible initially."""
        # Results frame should exist but not be gridded
        assert hasattr(self.tab, 'results_frame')
        # Check that it's not mapped (visible)
        info = self.tab.results_frame.grid_info()
        assert len(info) == 0  # Not gridded means hidden

    def test_get_text_excludes_placeholder(self):
        """Test that _get_text returns empty when placeholder is shown."""
        # With placeholder
        text = self.tab._get_text()
        assert text == ""

    def test_get_text_returns_actual_content(self):
        """Test that _get_text returns actual text content."""
        # Clear and add real text
        self.tab.text_input.delete('1.0', 'end')
        self.tab.text_input.insert('1.0', 'Das ist ein Test.')
        self.tab.text_input.configure(foreground='black')

        text = self.tab._get_text()
        assert text == "Das ist ein Test."

    def test_results_labels_exist(self):
        """Test that all result labels are present."""
        assert hasattr(self.tab, 'session_id_label')
        assert hasattr(self.tab, 'words_processed_label')
        assert hasattr(self.tab, 'words_added_label')
        assert hasattr(self.tab, 'words_translated_label')
        assert hasattr(self.tab, 'success_label')

    def test_review_link_button_exists(self):
        """Test that review queue link button exists."""
        assert hasattr(self.tab, 'review_link')


class TestTextProcessingTabBehavior:
    """Test Text Processing tab behavior."""

    def setup_method(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.notebook = tk.ttk.Notebook(self.root)
        self.tab = TextProcessingTab(self.notebook, notebook=self.notebook)
        self.root.update_idletasks()

    def teardown_method(self):
        """Clean up after tests."""
        self.root.destroy()

    def test_empty_text_shows_warning(self):
        """Test that processing empty text shows a warning."""
        with patch('tkinter.messagebox.showwarning') as mock_warning:
            # Try to process with placeholder text
            self.tab._process_text()
            mock_warning.assert_called_once()
            assert 'Empty' in mock_warning.call_args[0][0]

    def test_button_disabled_during_processing(self):
        """Test that buttons are disabled during processing."""
        # Mock the process_text_input to avoid actual processing
        with patch('tabs.text_processing_tab.process_text_input') as mock_process:
            # Set up some text
            self.tab.text_input.delete('1.0', 'end')
            self.tab.text_input.insert('1.0', 'Test text')
            self.tab.text_input.configure(foreground='black')

            # Make the mock not return immediately
            mock_process.return_value = {
                'session_id': 'test',
                'words_processed': 1,
                'words_added': 1,
                'words_translated': 0
            }

            # Start processing
            self.tab._process_text()

            # Check button state
            assert self.tab._is_processing is True
            assert 'disabled' in str(self.tab.process_button['state'])
            assert 'disabled' in str(self.tab.clear_button['state'])

    def test_processing_complete_shows_results(self):
        """Test that successful processing displays results."""
        result = {
            'session_id': 'test_session_123',
            'words_processed': 10,
            'words_added': 5,
            'words_translated': 3
        }

        self.tab._on_processing_complete(result)

        # Check that results are displayed
        assert self.tab.session_id_label.cget('text') == 'test_session_123'
        assert self.tab.words_processed_label.cget('text') == '10'
        assert self.tab.words_added_label.cget('text') == '5'
        assert self.tab.words_translated_label.cget('text') == '3'

    def test_processing_complete_shows_success_message(self):
        """Test that success message is shown after processing."""
        result = {
            'session_id': 'test',
            'words_processed': 5,
            'words_added': 3,
            'words_translated': 2
        }

        self.tab._on_processing_complete(result)

        success_text = self.tab.success_label.cget('text')
        assert '3' in success_text
        assert 'Successfully' in success_text

    def test_processing_no_new_words_message(self):
        """Test message when no new words are found."""
        result = {
            'session_id': 'test',
            'words_processed': 0,
            'words_added': 0,
            'words_translated': 0
        }

        self.tab._on_processing_complete(result)

        success_text = self.tab.success_label.cget('text')
        assert 'No new words' in success_text or 'already known' in success_text

    def test_processing_error_shows_message(self):
        """Test that processing errors are displayed."""
        with patch('tkinter.messagebox.showerror') as mock_error:
            self.tab._is_processing = True
            self.tab._on_processing_error("Test error message")

            mock_error.assert_called_once()
            assert 'error' in mock_error.call_args[0][0].lower()
            assert 'Test error message' in mock_error.call_args[0][1]

    def test_buttons_reenabled_after_error(self):
        """Test that buttons are re-enabled after an error."""
        self.tab._is_processing = True
        self.tab.process_button.configure(state='disabled')
        self.tab.clear_button.configure(state='disabled')

        self.tab._on_processing_error("Error")

        assert self.tab._is_processing is False
        assert str(self.tab.process_button['state']) in ['normal', 'enabled', '!disabled']

    def test_none_result_shows_warning(self):
        """Test that None result shows warning message."""
        with patch('tkinter.messagebox.showwarning') as mock_warning:
            self.tab._on_processing_complete(None)
            mock_warning.assert_called_once()
            assert 'Failed' in mock_warning.call_args[0][0]


class TestPlaceholderBehavior:
    """Test placeholder text behavior."""

    def setup_method(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.notebook = tk.ttk.Notebook(self.root)
        self.tab = TextProcessingTab(self.notebook, notebook=self.notebook)
        self.root.update_idletasks()

    def teardown_method(self):
        """Clean up after tests."""
        self.root.destroy()

    def test_placeholder_removed_on_focus(self):
        """Test that placeholder is removed when text area gets focus."""
        # Simulate focus in
        event = MagicMock()
        self.tab._on_focus_in(event)

        # Check placeholder is removed
        text = self.tab.text_input.get('1.0', 'end-1c')
        assert text == ""

    def test_placeholder_restored_on_focus_out_if_empty(self):
        """Test that placeholder is restored when focus leaves empty text area."""
        # First remove placeholder
        self.tab.text_input.delete('1.0', 'end')

        # Simulate focus out
        event = MagicMock()
        self.tab._on_focus_out(event)

        # Check placeholder is restored
        text = self.tab.text_input.get('1.0', 'end-1c')
        assert text == "Paste German text here..."

    def test_placeholder_not_restored_if_has_content(self):
        """Test that placeholder is not restored if text area has content."""
        # Clear and add content
        self.tab.text_input.delete('1.0', 'end')
        self.tab.text_input.insert('1.0', 'User typed text')

        # Simulate focus out
        event = MagicMock()
        self.tab._on_focus_out(event)

        # Check content is preserved
        text = self.tab.text_input.get('1.0', 'end-1c')
        assert text == "User typed text"


def run_tests():
    """Run all tests."""
    import pytest
    pytest.main([__file__, '-v'])


if __name__ == "__main__":
    run_tests()
