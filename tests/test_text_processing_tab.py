"""Test the Text Processing tab UI and behavior."""

import sys
import os
import tkinter as tk
import pytest
from unittest.mock import patch

# Add src/ui and src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'ui'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tabs.text_processing_tab import TextProcessingTab


def create_root():
    """Create a Tk root or skip tests if Tk is unavailable."""
    _configure_tk_paths()
    try:
        return tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk not available: {exc}")


def _configure_tk_paths():
    """Configure Tcl/Tk library paths for environments missing defaults."""
    if os.environ.get("TCL_LIBRARY") and os.environ.get("TK_LIBRARY"):
        return

    candidates = [
        os.path.join(sys.prefix, 'Library', 'lib'),
        os.path.join(sys.prefix, 'tcl'),
    ]

    envs_dir = os.path.join(sys.prefix, 'envs')
    if os.path.isdir(envs_dir):
        for env_name in os.listdir(envs_dir):
            env_lib = os.path.join(envs_dir, env_name, 'Library', 'lib')
            candidates.append(env_lib)

    for base in candidates:
        tcl_path = os.path.join(base, 'tcl8.6')
        tk_path = os.path.join(base, 'tk8.6')
        if os.path.exists(tcl_path) and os.path.exists(tk_path):
            os.environ.setdefault("TCL_LIBRARY", tcl_path)
            os.environ.setdefault("TK_LIBRARY", tk_path)
            return


class TestTextProcessingTabUI:
    """Test Text Processing tab UI elements."""

    def setup_method(self):
        """Set up test fixtures."""
        self.root = create_root()
        self.tab = TextProcessingTab(self.root)
        self.tab.pack()
        self.root.update_idletasks()

    def teardown_method(self):
        """Clean up after tests."""
        self.root.destroy()

    def test_placeholder_set_on_init(self):
        """Placeholder text should be present initially."""
        content = self.tab.text_widget.get('1.0', 'end').strip()
        assert content == self.tab._placeholder_text
        assert self.tab._placeholder_active is True

    def test_results_hidden_initially(self):
        """Results frame should start hidden."""
        assert not self.tab.results_frame.winfo_ismapped()

    def test_clear_button_restores_placeholder_and_hides_results(self):
        """Clear should reset text and hide results."""
        # Show results then clear
        self.tab._show_results({
            'session_id': 'session_test',
            'words_processed': 2,
            'words_added': 2,
            'words_translated': 1
        })
        self.root.update()
        assert self.tab.results_frame.winfo_ismapped()

        # Simulate user text to disable placeholder before clearing
        self.tab.text_widget.delete('1.0', 'end')
        self.tab.text_widget.insert('1.0', 'Hallo Welt')
        self.tab._placeholder_active = False

        self.tab._clear_text()

        content = self.tab.text_widget.get('1.0', 'end').strip()
        assert content == self.tab._placeholder_text
        assert self.tab._placeholder_active is True
        assert not self.tab.results_frame.winfo_ismapped()


class TestTextProcessingTabBehavior:
    """Test Text Processing tab processing behavior."""

    def setup_method(self):
        """Set up test fixtures."""
        self.root = create_root()
        self.tab = TextProcessingTab(self.root)
        self.tab.pack()
        self.root.update_idletasks()

    def teardown_method(self):
        """Clean up after tests."""
        self.root.destroy()

    @patch('tabs.text_processing_tab.messagebox.showerror')
    @patch('tabs.text_processing_tab.process_text_input')
    def test_process_text_calls_backend_and_shows_results(self, mock_process, mock_error):
        """Processing should call backend and reveal results."""
        mock_process.return_value = {
            'session_id': 'session_123',
            'words_processed': 3,
            'words_added': 2,
            'words_translated': 1
        }

        # Simulate user entering text (remove placeholder state)
        self.tab.text_widget.delete('1.0', 'end')
        self.tab.text_widget.insert('1.0', 'Ein kurzer Test.')
        self.tab._placeholder_active = False

        self.tab._on_process_click()
        self.root.update()

        mock_error.assert_not_called()
        mock_process.assert_called_once_with('Ein kurzer Test.')
        assert self.tab.results_frame.winfo_ismapped()
        assert self.tab.session_value.cget('text') == 'session_123'
        assert self.tab.words_processed_value.cget('text') == '3'

    @patch('tabs.text_processing_tab.messagebox.showerror')
    @patch('tabs.text_processing_tab.process_text_input')
    def test_process_text_shows_error_on_empty_input(self, mock_process, mock_error):
        """Empty text should not trigger backend call."""
        self.tab._set_placeholder()  # Ensure placeholder active

        self.tab._on_process_click()

        mock_process.assert_not_called()
        mock_error.assert_called_once()
        assert not self.tab.results_frame.winfo_ismapped()

    def test_process_button_disabled_during_processing(self):
        """Process button should be disabled while processing runs."""
        def fake_process(_text):
            # Button should be disabled during processing
            assert 'disabled' in str(self.tab.process_button['state'])
            return {
                'session_id': 'session_fake',
                'words_processed': 1,
                'words_added': 1,
                'words_translated': 0
            }

        with patch('tabs.text_processing_tab.process_text_input', side_effect=fake_process):
            self.tab.text_widget.delete('1.0', 'end')
            self.tab.text_widget.insert('1.0', 'Beispieltext')
            self.tab._placeholder_active = False

            self.tab._on_process_click()

            assert 'disabled' not in str(self.tab.process_button['state'])
            assert self.tab.process_button.cget('text') == "Process Text"
