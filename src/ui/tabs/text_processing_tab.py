"""Text Processing tab placeholder."""

import tkinter as tk
from tkinter import ttk


class TextProcessingTab(ttk.Frame):
    """Placeholder for Text Processing tab."""

    def __init__(self, parent):
        """Initialize the Text Processing tab.

        Args:
            parent: Parent widget (notebook)
        """
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Set up the placeholder UI."""
        label = ttk.Label(
            self,
            text="Text Processing - Coming Soon",
            font=('Arial', 14)
        )
        label.pack(expand=True)
