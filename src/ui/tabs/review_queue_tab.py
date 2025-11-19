"""Review Queue tab for reviewing and approving/rejecting processed words."""

import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from database import get_all_sessions, get_pending_words, approve_word, reject_word


class ReviewQueueTab(ttk.Frame):
    """Tab for reviewing and approving/rejecting words from processing sessions."""

    def __init__(self, parent):
        """Initialize the Review Queue tab.

        Args:
            parent: Parent widget (notebook)
        """
        super().__init__(parent)

        # State management
        self._current_session_id = None
        self._words = []
        self._current_index = 0
        self._difficulty = tk.IntVar(value=3)  # Default: Medium

        self._setup_ui()
        self._update_button_states()

    def _setup_ui(self):
        """Set up the tab UI with session selector, word display, and actions."""
        # Main container with padding
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill='both', expand=True)

        # Configure grid weights for responsive layout
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Top Section - Session Selection
        self._create_session_section(main_frame)

        # Middle Section - Word Display
        self._create_word_display_section(main_frame)

        # Bottom Section - Actions
        self._create_actions_section(main_frame)

    def _create_session_section(self, parent):
        """Create the session selection section."""
        session_frame = ttk.LabelFrame(parent, text="Session Selection", padding="10")
        session_frame.grid(row=0, column=0, sticky='ew', pady=(0, 10))
        session_frame.columnconfigure(1, weight=1)

        # Session dropdown
        ttk.Label(session_frame, text="Session:").grid(row=0, column=0, padx=(0, 10))

        self.session_combo = ttk.Combobox(session_frame, state='readonly', width=50)
        self.session_combo.grid(row=0, column=1, sticky='ew', padx=(0, 10))

        # Load Session button
        self.load_button = ttk.Button(
            session_frame,
            text="Load Session",
            command=self._load_session
        )
        self.load_button.grid(row=0, column=2, padx=(0, 10))

        # Refresh button
        self.refresh_button = ttk.Button(
            session_frame,
            text="Refresh",
            command=self._refresh_sessions
        )
        self.refresh_button.grid(row=0, column=3)

        # Progress label
        self.progress_label = ttk.Label(
            session_frame,
            text="No session loaded",
            font=('Arial', 10)
        )
        self.progress_label.grid(row=1, column=0, columnspan=4, sticky='w', pady=(10, 0))

    def _create_word_display_section(self, parent):
        """Create the word display section."""
        word_frame = ttk.LabelFrame(parent, text="Word Details", padding="20")
        word_frame.grid(row=1, column=0, sticky='nsew', pady=(0, 10))
        word_frame.columnconfigure(1, weight=1)

        # Original form
        ttk.Label(word_frame, text="Original:", font=('Arial', 10, 'bold')).grid(
            row=0, column=0, sticky='w', pady=5
        )
        self.original_label = ttk.Label(word_frame, text="-", font=('Arial', 10))
        self.original_label.grid(row=0, column=1, sticky='w', pady=5)

        # Lemma (main word)
        ttk.Label(word_frame, text="Lemma:", font=('Arial', 10, 'bold')).grid(
            row=1, column=0, sticky='w', pady=5
        )
        self.lemma_label = ttk.Label(word_frame, text="-", font=('Arial', 14, 'bold'))
        self.lemma_label.grid(row=1, column=1, sticky='w', pady=5)

        # Part of Speech
        ttk.Label(word_frame, text="POS:", font=('Arial', 10, 'bold')).grid(
            row=2, column=0, sticky='w', pady=5
        )
        self.pos_label = ttk.Label(word_frame, text="-", font=('Arial', 10))
        self.pos_label.grid(row=2, column=1, sticky='w', pady=5)

        # Translation
        ttk.Label(word_frame, text="Translation:", font=('Arial', 10, 'bold')).grid(
            row=3, column=0, sticky='w', pady=5
        )
        self.translation_label = ttk.Label(word_frame, text="-", font=('Arial', 10))
        self.translation_label.grid(row=3, column=1, sticky='w', pady=5)

        # No word message (shown when no words to display)
        self.no_word_label = ttk.Label(
            word_frame,
            text="Load a session to review words",
            font=('Arial', 12),
            foreground='gray'
        )
        self.no_word_label.grid(row=4, column=0, columnspan=2, pady=20)

    def _create_actions_section(self, parent):
        """Create the actions section with difficulty, tags, and buttons."""
        actions_frame = ttk.LabelFrame(parent, text="Actions", padding="10")
        actions_frame.grid(row=2, column=0, sticky='ew')
        actions_frame.columnconfigure(0, weight=1)

        # Difficulty selection
        difficulty_frame = ttk.Frame(actions_frame)
        difficulty_frame.grid(row=0, column=0, sticky='w', pady=(0, 10))

        ttk.Label(difficulty_frame, text="Difficulty:", font=('Arial', 10, 'bold')).pack(side='left', padx=(0, 10))

        difficulty_options = [
            (0, "Known"),
            (1, "Super Easy"),
            (2, "Easy"),
            (3, "Medium"),
            (4, "Hard")
        ]

        for value, text in difficulty_options:
            rb = ttk.Radiobutton(
                difficulty_frame,
                text=text,
                variable=self._difficulty,
                value=value
            )
            rb.pack(side='left', padx=5)

        # Tags entry
        tags_frame = ttk.Frame(actions_frame)
        tags_frame.grid(row=1, column=0, sticky='ew', pady=(0, 10))
        tags_frame.columnconfigure(1, weight=1)

        ttk.Label(tags_frame, text="Tags:", font=('Arial', 10, 'bold')).grid(
            row=0, column=0, sticky='w', padx=(0, 10)
        )
        self.tags_entry = ttk.Entry(tags_frame)
        self.tags_entry.grid(row=0, column=1, sticky='ew')
        ttk.Label(
            tags_frame,
            text="(comma-separated, optional)",
            font=('Arial', 8),
            foreground='gray'
        ).grid(row=0, column=2, padx=(5, 0))

        # Action buttons
        button_frame = ttk.Frame(actions_frame)
        button_frame.grid(row=2, column=0, sticky='e')

        # Skip button
        self.skip_button = ttk.Button(
            button_frame,
            text="Skip",
            command=self._skip_word,
            width=10
        )
        self.skip_button.pack(side='left', padx=5)

        # Reject button
        self.reject_button = ttk.Button(
            button_frame,
            text="Reject",
            command=self._reject_word,
            width=10
        )
        self.reject_button.pack(side='left', padx=5)

        # Approve button
        self.approve_button = ttk.Button(
            button_frame,
            text="Approve",
            command=self._approve_word,
            width=10
        )
        self.approve_button.pack(side='left', padx=5)

        # Apply styles for button colors
        try:
            style = ttk.Style()
            style.configure('Approve.TButton', font=('Arial', 10, 'bold'))
            style.configure('Reject.TButton', font=('Arial', 10))
            self.approve_button.configure(style='Approve.TButton')
            self.reject_button.configure(style='Reject.TButton')
        except tk.TclError:
            pass  # Style may not be supported on all platforms

    def _refresh_sessions(self):
        """Refresh the list of available sessions."""
        sessions = get_all_sessions()

        if not sessions:
            self.session_combo['values'] = []
            self.session_combo.set('')
            messagebox.showinfo(
                "No Sessions",
                "No processing sessions found. Process some text first."
            )
            return

        # Format sessions for display: "session_id (X words)"
        session_values = []
        self._session_map = {}  # Map display text to session_id

        for session_id, word_count, created_at in sessions:
            display_text = f"{session_id} ({word_count} words)"
            session_values.append(display_text)
            self._session_map[display_text] = session_id

        self.session_combo['values'] = session_values
        if session_values:
            self.session_combo.current(0)

    def _load_session(self):
        """Load the selected session and display the first word."""
        selected = self.session_combo.get()
        if not selected:
            messagebox.showwarning(
                "No Session",
                "Please select a session to load."
            )
            return

        # Get session_id from selection
        if not hasattr(self, '_session_map') or selected not in self._session_map:
            self._refresh_sessions()
            return

        session_id = self._session_map[selected]

        # Load words for this session
        words = get_pending_words(session_id)

        if not words:
            messagebox.showinfo(
                "Empty Session",
                "This session has no pending words to review."
            )
            return

        # Update state
        self._current_session_id = session_id
        self._words = words
        self._current_index = 0

        # Display first word
        self._display_current_word()
        self._update_button_states()

    def _display_current_word(self):
        """Display the current word in the word display section."""
        if not self._words or self._current_index >= len(self._words):
            self._show_session_complete()
            return

        # Hide the "no word" message
        self.no_word_label.grid_remove()

        # Get current word data
        # Format: (word, lemma, pos, translation, is_regular, session_id, created_at)
        word_data = self._words[self._current_index]
        original, lemma, pos, translation, is_regular, session_id, created_at = word_data

        # Update labels
        self.original_label.configure(text=original)
        self.lemma_label.configure(text=lemma)
        self.pos_label.configure(text=pos or "-")
        self.translation_label.configure(
            text=translation if translation else "No translation",
            foreground='black' if translation else 'gray'
        )

        # Update progress
        self._update_progress()

        # Reset difficulty to default and clear tags
        self._difficulty.set(3)
        self.tags_entry.delete(0, 'end')

    def _update_progress(self):
        """Update the progress label."""
        if self._words:
            total = len(self._words)
            current = self._current_index + 1
            self.progress_label.configure(text=f"Word {current} of {total}")
        else:
            self.progress_label.configure(text="No session loaded")

    def _update_button_states(self):
        """Enable or disable action buttons based on current state."""
        has_words = bool(self._words) and self._current_index < len(self._words)

        state = 'normal' if has_words else 'disabled'
        self.approve_button.configure(state=state)
        self.reject_button.configure(state=state)
        self.skip_button.configure(state=state)

    def _get_tags(self):
        """Get the list of tags from the entry field."""
        tags_text = self.tags_entry.get().strip()
        if not tags_text:
            return None

        # Split by comma and clean up each tag
        tags = [tag.strip() for tag in tags_text.split(',')]
        # Remove empty strings
        tags = [tag for tag in tags if tag]

        return tags if tags else None

    def _approve_word(self):
        """Approve the current word and move to the next."""
        if not self._words or self._current_index >= len(self._words):
            return

        # Get current word lemma
        word_data = self._words[self._current_index]
        lemma = word_data[1]  # lemma is at index 1

        # Get difficulty and tags
        difficulty = self._difficulty.get()
        tags = self._get_tags()

        # Approve the word
        success = approve_word(lemma, self._current_session_id, difficulty, tags)

        if success:
            # Move to next word
            self._current_index += 1
            self._display_current_word()
            self._update_button_states()
        else:
            messagebox.showerror(
                "Approval Failed",
                f"Failed to approve word '{lemma}'. It may already exist in the vocabulary."
            )
            # Still move to next word since it was removed from temp
            self._current_index += 1
            self._display_current_word()
            self._update_button_states()

    def _reject_word(self):
        """Reject the current word and move to the next."""
        if not self._words or self._current_index >= len(self._words):
            return

        # Get current word lemma
        word_data = self._words[self._current_index]
        lemma = word_data[1]  # lemma is at index 1

        # Reject the word
        success = reject_word(lemma, self._current_session_id)

        if success:
            # Move to next word
            self._current_index += 1
            self._display_current_word()
            self._update_button_states()
        else:
            messagebox.showerror(
                "Rejection Failed",
                f"Failed to reject word '{lemma}'."
            )

    def _skip_word(self):
        """Skip the current word and move to the next without action."""
        if not self._words or self._current_index >= len(self._words):
            return

        # Simply move to next word
        self._current_index += 1
        self._display_current_word()
        self._update_button_states()

    def _show_session_complete(self):
        """Show the session complete message."""
        # Clear word display
        self.original_label.configure(text="-")
        self.lemma_label.configure(text="-")
        self.pos_label.configure(text="-")
        self.translation_label.configure(text="-", foreground='black')

        # Show completion message
        self.no_word_label.configure(
            text="Session complete! All words have been reviewed.",
            foreground='green'
        )
        self.no_word_label.grid()

        # Update progress
        self.progress_label.configure(text="Session complete")

        # Disable action buttons
        self._update_button_states()

        # Clear session state
        self._words = []
        self._current_session_id = None

    def refresh(self):
        """Public method to refresh the sessions list (can be called from other tabs)."""
        self._refresh_sessions()
