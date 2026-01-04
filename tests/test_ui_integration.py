"""UI integration tests covering end-to-end workflows."""

import os
import sys
import sqlite3
import tkinter as tk
import pytest

# Add src paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'ui'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import database  # noqa: E402
from database import (  # noqa: E402
    add_temp_word,
    add_word,
    get_all_words,
    get_all_sessions,
    get_pending_words
)
from tabs.text_processing_tab import TextProcessingTab  # noqa: E402
from tabs.review_queue_tab import ReviewQueueTab  # noqa: E402
from tabs.vocabulary_tab import VocabularyTab  # noqa: E402


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


def create_root():
    """Create a Tk root or skip tests if Tk is unavailable."""
    _configure_tk_paths()
    try:
        return tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk not available: {exc}")


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Use a temporary database for each test."""
    db_path = tmp_path / "vocab.db"
    monkeypatch.setattr(database, "DB_FILE", str(db_path), raising=False)
    os.makedirs(tmp_path, exist_ok=True)
    database.init_database()
    yield


@pytest.fixture
def tk_root():
    """Provide a Tk root window."""
    root = create_root()
    yield root
    root.destroy()


def clear_tables():
    """Remove all rows from vocabulary-related tables."""
    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM temp_vocab")
        cursor.execute("DELETE FROM word_tags")
        cursor.execute("DELETE FROM tags")
        cursor.execute(f"DELETE FROM {database.TABLE_NAME}")
        conn.commit()


def test_text_processing_workflow_creates_session_and_temp_words(tk_root, monkeypatch):
    """Processing text via the tab should store temp words and show results."""
    clear_tables()
    session_id = "session_ui_test"

    def fake_process_text_input(text):
        add_temp_word("Hund", "der Hund", "NOUN", "dog", True, session_id)
        add_temp_word("Katze", "die Katze", "NOUN", "cat", True, session_id)
        return {
            'session_id': session_id,
            'words_processed': 2,
            'words_added': 2,
            'words_translated': 2
        }

    monkeypatch.setattr("tabs.text_processing_tab.process_text_input", fake_process_text_input)
    monkeypatch.setattr("tabs.text_processing_tab.messagebox.showerror", lambda *args, **kwargs: None)

    tab = TextProcessingTab(tk_root)
    tab.pack()
    tab.text_widget.delete('1.0', 'end')
    tab.text_widget.insert('1.0', 'Das ist ein Testtext.')
    tab._placeholder_active = False

    tab._on_process_click()
    tk_root.update()

    pending = get_pending_words(session_id)
    assert len(pending) == 2
    assert tab.session_value.cget('text') == session_id
    assert tab.results_frame.winfo_ismapped()


def test_review_queue_workflow_approve_and_reject(tk_root, monkeypatch):
    """Review Queue tab should approve and reject words correctly."""
    clear_tables()
    session_id = "session_review"
    add_temp_word("Hund", "der Hund", "NOUN", "dog", True, session_id)
    add_temp_word("Katze", "die Katze", "NOUN", "cat", True, session_id)

    monkeypatch.setattr("tabs.review_queue_tab.messagebox.showinfo", lambda *args, **kwargs: None)
    monkeypatch.setattr("tabs.review_queue_tab.messagebox.showwarning", lambda *args, **kwargs: None)
    monkeypatch.setattr("tabs.review_queue_tab.messagebox.showerror", lambda *args, **kwargs: None)

    tab = ReviewQueueTab(tk_root)
    tab.pack()

    tab._refresh_sessions()
    tk_root.update()
    assert tab.session_combo['values']

    tab.session_combo.current(0)
    tab._load_session()
    tk_root.update()

    # Approve first word
    tab._difficulty.set(2)
    tab._approve_word()

    # Reject second word
    tab._reject_word()

    # After processing both words, temp should be empty and vocab should contain approved lemma
    remaining = get_pending_words(session_id)
    assert remaining == []

    vocab_words = get_all_words()
    lemma_list = [row[0] for row in vocab_words]
    assert "der Hund" in lemma_list


def test_vocabulary_tab_displays_and_filters(tk_root):
    """Vocabulary tab should display words and filter by search."""
    clear_tables()
    add_word("der Hund", "NOUN", True, "dog", 2)
    add_word("laufen", "VERB", True, "run", 3)

    tab = VocabularyTab(tk_root)
    tab.pack()
    tk_root.update()

    all_items = tab.tree.get_children()
    assert len(all_items) == 2

    # Apply search filter
    tab.search_var.set("Hund")
    tab._filter_data()
    filtered_items = tab.tree.get_children()
    assert len(filtered_items) == 1


def test_text_processing_empty_input_shows_error(tk_root, monkeypatch):
    """Empty text should surface a user-friendly error."""
    clear_tables()
    error_called = {}

    def fake_error(title, message):
        error_called['called'] = True
        error_called['title'] = title
        error_called['message'] = message

    monkeypatch.setattr("tabs.text_processing_tab.messagebox.showerror", fake_error)

    tab = TextProcessingTab(tk_root)
    tab.pack()
    tab._set_placeholder()

    tab._on_process_click()
    assert error_called.get('called') is True
    assert not tab.results_frame.winfo_ismapped()
    assert get_pending_words() == []


def test_complete_workflow_process_review_and_view(tk_root, monkeypatch):
    """Full flow: process text -> review -> approve -> view in vocabulary."""
    clear_tables()
    session_id = "session_complete"

    def fake_process_text_input(text):
        add_temp_word("Baum", "der Baum", "NOUN", "tree", True, session_id)
        return {
            'session_id': session_id,
            'words_processed': 1,
            'words_added': 1,
            'words_translated': 1
        }

    monkeypatch.setattr("tabs.text_processing_tab.process_text_input", fake_process_text_input)
    monkeypatch.setattr("tabs.text_processing_tab.messagebox.showerror", lambda *args, **kwargs: None)
    monkeypatch.setattr("tabs.review_queue_tab.messagebox.showinfo", lambda *args, **kwargs: None)
    monkeypatch.setattr("tabs.review_queue_tab.messagebox.showwarning", lambda *args, **kwargs: None)
    monkeypatch.setattr("tabs.review_queue_tab.messagebox.showerror", lambda *args, **kwargs: None)

    # Process text
    process_tab = TextProcessingTab(tk_root)
    process_tab.pack()
    process_tab.text_widget.delete('1.0', 'end')
    process_tab.text_widget.insert('1.0', 'Ein einzelner Satz.')
    process_tab._placeholder_active = False
    process_tab._on_process_click()
    tk_root.update()

    # Review and approve
    review_tab = ReviewQueueTab(tk_root)
    review_tab.pack()
    review_tab._refresh_sessions()
    review_tab.session_combo.current(0)
    review_tab._load_session()
    review_tab._approve_word()
    tk_root.update()

    # Verify vocabulary displays approved word
    vocab_tab = VocabularyTab(tk_root)
    vocab_tab.pack()
    tk_root.update()
    items = vocab_tab.tree.get_children()
    values = [vocab_tab.tree.item(i)['values'][0] for i in items]
    assert "der Baum" in values
