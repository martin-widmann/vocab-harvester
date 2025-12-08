"""Vocabulary Database tab for viewing and searching approved vocabulary."""

import sys
import os
import tkinter as tk
from tkinter import ttk

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from database import get_all_words, get_word_tags, get_word_count


class VocabularyTab(ttk.Frame):
    """Tab for viewing and searching all approved vocabulary."""

    def __init__(self, parent):
        """Initialize the Vocabulary tab.

        Args:
            parent: Parent widget (notebook)
        """
        super().__init__(parent)

        # State management
        self._all_words = []  # Cache of all words for filtering
        self._sort_column = 'word'
        self._sort_reverse = False

        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        """Set up the tab UI with filters, treeview, and status bar."""
        # Main container with padding
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill='both', expand=True)

        # Configure grid weights for responsive layout
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Top Section - Filters
        self._create_filter_section(main_frame)

        # Middle Section - Data Display
        self._create_treeview_section(main_frame)

        # Bottom Section - Status
        self._create_status_section(main_frame)

    def _create_filter_section(self, parent):
        """Create the filter section with search bar, difficulty filter, and refresh button."""
        filter_frame = ttk.LabelFrame(parent, text="Filters", padding="10")
        filter_frame.grid(row=0, column=0, sticky='ew', pady=(0, 10))
        filter_frame.columnconfigure(1, weight=1)

        # Search bar
        ttk.Label(filter_frame, text="Search:").grid(row=0, column=0, padx=(0, 10))

        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(filter_frame, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=1, sticky='ew', padx=(0, 10))

        # Bind search to filter on key release
        self.search_var.trace('w', lambda *args: self._filter_data())

        # Difficulty filter dropdown
        ttk.Label(filter_frame, text="Difficulty:").grid(row=0, column=2, padx=(0, 10))

        self.difficulty_var = tk.StringVar(value="All")
        self.difficulty_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.difficulty_var,
            state='readonly',
            width=15,
            values=["All", "0-Known", "1-SuperEasy", "2-Easy", "3-Medium", "4-Hard"]
        )
        self.difficulty_combo.grid(row=0, column=3, padx=(0, 10))
        self.difficulty_combo.bind('<<ComboboxSelected>>', lambda e: self._load_data())

        # Refresh button
        self.refresh_button = ttk.Button(
            filter_frame,
            text="Refresh",
            command=self._load_data
        )
        self.refresh_button.grid(row=0, column=4)

    def _create_treeview_section(self, parent):
        """Create the treeview section with data table and scrollbars."""
        # Frame for treeview and scrollbars
        tree_frame = ttk.Frame(parent)
        tree_frame.grid(row=1, column=0, sticky='nsew')
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        # Create treeview with columns
        columns = ('word', 'pos', 'translation', 'difficulty', 'tags')
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings')

        # Configure column headings and widths
        self.tree.heading('word', text='Word', command=lambda: self._sort_by_column('word'))
        self.tree.heading('pos', text='POS', command=lambda: self._sort_by_column('pos'))
        self.tree.heading('translation', text='Translation', command=lambda: self._sort_by_column('translation'))
        self.tree.heading('difficulty', text='Difficulty', command=lambda: self._sort_by_column('difficulty'))
        self.tree.heading('tags', text='Tags', command=lambda: self._sort_by_column('tags'))

        self.tree.column('word', width=200, minwidth=100)
        self.tree.column('pos', width=80, minwidth=50)
        self.tree.column('translation', width=200, minwidth=100)
        self.tree.column('difficulty', width=80, minwidth=50)
        self.tree.column('tags', width=150, minwidth=100)

        # Add scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Grid layout for treeview and scrollbars
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        # Configure alternating row colors using tags
        self.tree.tag_configure('oddrow', background='#f0f0f0')
        self.tree.tag_configure('evenrow', background='#ffffff')

        # Bind double-click for word details (optional enhancement)
        self.tree.bind('<Double-1>', self._show_word_details)

    def _create_status_section(self, parent):
        """Create the status bar section."""
        status_frame = ttk.Frame(parent)
        status_frame.grid(row=2, column=0, sticky='ew', pady=(10, 0))

        self.status_label = ttk.Label(
            status_frame,
            text="Total words: 0",
            font=('Arial', 9)
        )
        self.status_label.pack(side='left')

    def _load_data(self):
        """Load data from database and populate treeview."""
        # Get difficulty filter
        difficulty_filter = None
        difficulty_text = self.difficulty_var.get()
        if difficulty_text != "All":
            # Extract number from "0-Known", "1-SuperEasy", etc.
            difficulty_filter = int(difficulty_text.split('-')[0])

        # Build filters dict
        filters = {}
        if difficulty_filter is not None:
            filters['difficulty'] = difficulty_filter

        # Get words from database
        words = get_all_words(filters=filters if filters else None)

        # Store for filtering and enrich with tags
        self._all_words = []
        for word_data in words:
            word, pos, is_regular, translation, difficulty = word_data

            # Get tags for this word
            word_tags = get_word_tags(word)
            tags_str = ', '.join([tag[0] for tag in word_tags]) if word_tags else ''

            self._all_words.append({
                'word': word,
                'pos': pos or '',
                'translation': translation or '',
                'difficulty': difficulty,
                'tags': tags_str
            })

        # Apply search filter and update display
        self._filter_data()

    def _filter_data(self):
        """Filter data based on search term and update treeview."""
        search_term = self.search_var.get().lower().strip()

        # Filter words based on search term
        if search_term:
            filtered_words = [
                w for w in self._all_words
                if search_term in w['word'].lower() or
                   search_term in w['translation'].lower() or
                   search_term in w['tags'].lower()
            ]
        else:
            filtered_words = self._all_words

        # Sort the filtered data
        filtered_words = self._sort_data(filtered_words)

        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Populate treeview with filtered data
        for i, word_data in enumerate(filtered_words):
            # Alternate row colors
            tag = 'oddrow' if i % 2 else 'evenrow'

            self.tree.insert(
                '',
                'end',
                values=(
                    word_data['word'],
                    word_data['pos'],
                    word_data['translation'],
                    word_data['difficulty'],
                    word_data['tags']
                ),
                tags=(tag,)
            )

        # Update status bar
        total = len(self._all_words)
        showing = len(filtered_words)
        if search_term or total != showing:
            self.status_label.configure(text=f"Showing {showing} of {total} words")
        else:
            self.status_label.configure(text=f"Total words: {total}")

    def _sort_data(self, data):
        """Sort data by current sort column and direction."""
        if not data:
            return data

        def sort_key(item):
            value = item.get(self._sort_column, '')
            # Handle numeric sorting for difficulty
            if self._sort_column == 'difficulty':
                return int(value) if value != '' else 0
            # Case-insensitive string sorting
            return str(value).lower()

        return sorted(data, key=sort_key, reverse=self._sort_reverse)

    def _sort_by_column(self, column):
        """Sort treeview by clicked column."""
        # Toggle sort direction if same column, otherwise reset to ascending
        if self._sort_column == column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column
            self._sort_reverse = False

        # Re-filter (which also sorts)
        self._filter_data()

    def _show_word_details(self, event):
        """Show details popup when word is double-clicked."""
        # Get selected item
        selection = self.tree.selection()
        if not selection:
            return

        item = self.tree.item(selection[0])
        values = item['values']
        if not values:
            return

        word, pos, translation, difficulty, tags = values

        # Create popup window
        popup = tk.Toplevel(self)
        popup.title(f"Word Details: {word}")
        popup.geometry("400x300")
        popup.resizable(False, False)

        # Center the popup
        popup.transient(self.winfo_toplevel())
        popup.grab_set()

        # Content frame
        content = ttk.Frame(popup, padding="20")
        content.pack(fill='both', expand=True)

        # Word details
        ttk.Label(content, text="Word:", font=('Arial', 10, 'bold')).grid(
            row=0, column=0, sticky='w', pady=5
        )
        ttk.Label(content, text=word, font=('Arial', 12, 'bold')).grid(
            row=0, column=1, sticky='w', pady=5, padx=(10, 0)
        )

        ttk.Label(content, text="POS:", font=('Arial', 10, 'bold')).grid(
            row=1, column=0, sticky='w', pady=5
        )
        ttk.Label(content, text=pos or '-').grid(
            row=1, column=1, sticky='w', pady=5, padx=(10, 0)
        )

        ttk.Label(content, text="Translation:", font=('Arial', 10, 'bold')).grid(
            row=2, column=0, sticky='w', pady=5
        )
        ttk.Label(content, text=translation or '-').grid(
            row=2, column=1, sticky='w', pady=5, padx=(10, 0)
        )

        # Map difficulty number to text
        difficulty_names = {
            0: "Known",
            1: "Super Easy",
            2: "Easy",
            3: "Medium",
            4: "Hard"
        }
        difficulty_text = difficulty_names.get(difficulty, str(difficulty))

        ttk.Label(content, text="Difficulty:", font=('Arial', 10, 'bold')).grid(
            row=3, column=0, sticky='w', pady=5
        )
        ttk.Label(content, text=difficulty_text).grid(
            row=3, column=1, sticky='w', pady=5, padx=(10, 0)
        )

        ttk.Label(content, text="Tags:", font=('Arial', 10, 'bold')).grid(
            row=4, column=0, sticky='w', pady=5
        )
        ttk.Label(content, text=tags or '-', wraplength=250).grid(
            row=4, column=1, sticky='w', pady=5, padx=(10, 0)
        )

        # Close button
        ttk.Button(
            content,
            text="Close",
            command=popup.destroy
        ).grid(row=5, column=0, columnspan=2, pady=(20, 0))

    def refresh(self):
        """Public method to refresh the data (can be called from other tabs)."""
        self._load_data()

    def on_tab_selected(self):
        """Called when this tab gains focus - auto-refresh data."""
        self._load_data()
