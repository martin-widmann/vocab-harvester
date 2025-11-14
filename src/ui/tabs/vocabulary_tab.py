"""Vocabulary tab placeholder."""

import tkinter as tk
from tkinter import ttk


class VocabularyTab(ttk.Frame):
    """Placeholder for Vocabulary tab."""

    def __init__(self, parent):
        """Initialize the Vocabulary tab.

        Args:
            parent: Parent widget (notebook)
        """
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Set up the placeholder UI."""
        label = ttk.Label(
            self,
            text="Vocabulary - Coming Soon",
            font=('Arial', 14)
        )
        label.pack(expand=True)
