"""Main application class for Vocab Harvester UI."""

import tkinter as tk
from tkinter import ttk
from tabs import TextProcessingTab, VocabularyTab, ReviewQueueTab


class VocabHarvesterApp:
    """Main Tkinter application for Vocab Harvester."""

    def __init__(self, root):
        """Initialize the Vocab Harvester application.

        Args:
            root: The root Tkinter window
        """
        self.root = root
        self._setup_window()
        self._setup_notebook()
        self._create_tabs()

    def _setup_window(self):
        """Configure the main window."""
        self.root.title("Vocab Harvester")
        self.root.geometry("900x600")

        # Make the window responsive
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

    def _setup_notebook(self):
        """Create and configure the notebook (tabbed interface)."""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both')

    def _create_tabs(self):
        """Create and add all tabs to the notebook."""
        # Text Processing Tab
        self.text_processing_tab = TextProcessingTab(self.notebook, notebook=self.notebook)
        self.notebook.add(self.text_processing_tab, text="Text Processing")

        # Vocabulary Tab
        self.vocabulary_tab = VocabularyTab(self.notebook)
        self.notebook.add(self.vocabulary_tab, text="Vocabulary")

        # Review Queue Tab
        self.review_queue_tab = ReviewQueueTab(self.notebook)
        self.notebook.add(self.review_queue_tab, text="Review Queue")

    def run(self):
        """Start the main event loop."""
        self.root.mainloop()
