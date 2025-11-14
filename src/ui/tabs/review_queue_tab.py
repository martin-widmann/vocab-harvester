"""Review Queue tab placeholder."""

import tkinter as tk
from tkinter import ttk


class ReviewQueueTab(ttk.Frame):
    """Placeholder for Review Queue tab."""

    def __init__(self, parent):
        """Initialize the Review Queue tab.

        Args:
            parent: Parent widget (notebook)
        """
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Set up the placeholder UI."""
        label = ttk.Label(
            self,
            text="Review Queue - Coming Soon",
            font=('Arial', 14)
        )
        label.pack(expand=True)
