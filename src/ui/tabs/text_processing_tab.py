"""Text Processing tab implementation."""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox

# Add src directory to path for parser import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from parser import process_text_input


class TextProcessingTab(ttk.Frame):
    """Tab for pasting and processing German text into the temp database."""

    def __init__(self, parent):
        """Initialize the Text Processing tab.

        Args:
            parent: Parent widget (notebook)
        """
        super().__init__(parent)
        self._placeholder_text = "Paste German text here..."
        self._placeholder_active = False
        self._is_processing = False

        self._setup_ui()
        self._set_placeholder()
        self._hide_results()

    def _setup_ui(self):
        """Set up the tab UI with text input, actions, and results."""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill='both', expand=True)

        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)

        # Input Section
        self._create_input_section(main_frame)

        # Results Section (initially hidden)
        self._create_results_section(main_frame)

    def _create_input_section(self, parent):
        """Create the text input area with controls."""
        input_frame = ttk.LabelFrame(parent, text="Text Input", padding="10")
        input_frame.grid(row=0, column=0, sticky='nsew')
        input_frame.columnconfigure(0, weight=1)
        input_frame.rowconfigure(1, weight=1, minsize=500)

        # Instruction label
        instruction = ttk.Label(
            input_frame,
            text="Paste German text below and process it into the review queue.",
            font=('Arial', 10)
        )
        instruction.grid(row=0, column=0, sticky='w', pady=(0, 10))

        # Text widget with scrollbar
        text_container = ttk.Frame(input_frame)
        text_container.grid(row=1, column=0, sticky='nsew')
        text_container.columnconfigure(0, weight=1)

        self.text_widget = tk.Text(
            text_container,
            wrap='word',
            height=20,
            font=('Arial', 11)
        )
        self.text_widget.grid(row=0, column=0, sticky='nsew')

        scrollbar = ttk.Scrollbar(
            text_container,
            orient='vertical',
            command=self.text_widget.yview
        )
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.text_widget.configure(yscrollcommand=scrollbar.set)

        # Placeholder handling
        self.text_widget.bind("<FocusIn>", self._on_focus_in)
        self.text_widget.bind("<FocusOut>", self._on_focus_out)

        # Action buttons
        button_frame = ttk.Frame(input_frame)
        button_frame.grid(row=2, column=0, sticky='e', pady=(10, 0))

        self.process_button = ttk.Button(
            button_frame,
            text="Process Text",
            command=self._on_process_click
        )
        self.process_button.grid(row=0, column=0, padx=(0, 10))

        self.clear_button = ttk.Button(
            button_frame,
            text="Clear",
            command=self._clear_text
        )
        self.clear_button.grid(row=0, column=1)

    def _create_results_section(self, parent):
        """Create the results display section."""
        self.results_frame = ttk.LabelFrame(parent, text="Results", padding="10")
        self.results_frame.grid(row=1, column=0, sticky='ew', pady=(10, 0))
        self.results_frame.columnconfigure(1, weight=1)

        ttk.Label(self.results_frame, text="Session ID:", font=('Arial', 10, 'bold')).grid(
            row=0, column=0, sticky='w', pady=5
        )
        self.session_value = ttk.Label(self.results_frame, text="-", font=('Arial', 10))
        self.session_value.grid(row=0, column=1, sticky='w', pady=5)

        ttk.Label(self.results_frame, text="Words processed:", font=('Arial', 10, 'bold')).grid(
            row=1, column=0, sticky='w', pady=5
        )
        self.words_processed_value = ttk.Label(self.results_frame, text="0", font=('Arial', 10))
        self.words_processed_value.grid(row=1, column=1, sticky='w', pady=5)

        ttk.Label(self.results_frame, text="Words added to review:", font=('Arial', 10, 'bold')).grid(
            row=2, column=0, sticky='w', pady=5
        )
        self.words_added_value = ttk.Label(self.results_frame, text="0", font=('Arial', 10))
        self.words_added_value.grid(row=2, column=1, sticky='w', pady=5)

        ttk.Label(self.results_frame, text="Auto-translated:", font=('Arial', 10, 'bold')).grid(
            row=3, column=0, sticky='w', pady=5
        )
        self.words_translated_value = ttk.Label(self.results_frame, text="0", font=('Arial', 10))
        self.words_translated_value.grid(row=3, column=1, sticky='w', pady=5)

        self.success_message = ttk.Label(
            self.results_frame,
            text="",
            font=('Arial', 10),
            foreground='green'
        )
        self.success_message.grid(row=4, column=0, columnspan=2, sticky='w', pady=(10, 0))

        self.review_button = ttk.Button(
            self.results_frame,
            text="Go to Review Queue",
            command=self._go_to_review_queue
        )
        self.review_button.grid(row=5, column=0, columnspan=2, sticky='w', pady=(10, 0))

    def _set_placeholder(self):
        """Insert placeholder text into the text widget."""
        self.text_widget.delete('1.0', 'end')
        self.text_widget.insert('1.0', self._placeholder_text)
        self.text_widget.configure(foreground='gray')
        self._placeholder_active = True

    def _on_focus_in(self, event):
        """Remove placeholder when the text widget gains focus."""
        if self._placeholder_active:
            self.text_widget.delete('1.0', 'end')
            self.text_widget.configure(foreground='black')
            self._placeholder_active = False

    def _on_focus_out(self, event):
        """Restore placeholder when focus is lost and text is empty."""
        if not self.text_widget.get('1.0', 'end').strip():
            self._set_placeholder()

    def _get_text_input(self):
        """Return the current text content without placeholder."""
        content = self.text_widget.get('1.0', 'end').strip()
        if self._placeholder_active:
            return ""
        return content

    def _clear_text(self):
        """Clear the text area and hide results."""
        self._set_placeholder()
        self._hide_results()

    def _hide_results(self):
        """Hide the results frame."""
        self.results_frame.grid_remove()

    def _show_results(self, result):
        """Display processing results."""
        self.session_value.configure(text=result.get('session_id', '-'))
        self.words_processed_value.configure(text=str(result.get('words_processed', 0)))
        self.words_added_value.configure(text=str(result.get('words_added', 0)))
        self.words_translated_value.configure(text=str(result.get('words_translated', 0)))

        if result.get('words_added', 0) == 0:
            message = "Processed successfully, but no new words were added."
        else:
            message = "Text processed successfully! Review the words in the Review Queue tab."

        self.success_message.configure(text=message)
        self.results_frame.grid()

    def _set_processing_state(self, is_processing):
        """Enable or disable processing state to prevent double clicks."""
        self._is_processing = is_processing
        state = ('disabled' if is_processing else 'normal')
        self.process_button.configure(state=state)
        self.clear_button.configure(state=state)
        if is_processing:
            self.process_button.configure(text="Processing...")
        else:
            self.process_button.configure(text="Process Text")

    def _on_process_click(self):
        """Handle the Process Text button click."""
        if self._is_processing:
            return

        text_content = self._get_text_input()
        if not text_content:
            messagebox.showerror(
                "No Text",
                "Please paste some German text to process."
            )
            return

        self._set_processing_state(True)
        try:
            result = process_text_input(text_content)
        except Exception as exc:  # noqa: BLE001 - show user-friendly error
            self._set_processing_state(False)
            messagebox.showerror(
                "Processing Failed",
                f"An error occurred while processing the text: {exc}"
            )
            return

        self._set_processing_state(False)

        if not result:
            messagebox.showwarning(
                "No Words Found",
                "No words could be processed from the provided text. Please try different text."
            )
            self._hide_results()
            return

        self._show_results(result)

    def _go_to_review_queue(self):
        """Switch to the Review Queue tab if available."""
        notebook = self._find_notebook()
        if not notebook:
            return

        for tab_id in notebook.tabs():
            if notebook.tab(tab_id, 'text') == "Review Queue":
                notebook.select(tab_id)
                break

    def _find_notebook(self):
        """Find the nearest ttk.Notebook in the widget hierarchy."""
        current = self.master
        while current is not None:
            if isinstance(current, ttk.Notebook):
                return current
            current = getattr(current, 'master', None)
        return None
