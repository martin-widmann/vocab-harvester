"""Text Processing tab for processing German text into vocabulary database."""

import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox
import threading

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from parser import process_text_input


class TextProcessingTab(ttk.Frame):
    """Tab for processing German text and extracting vocabulary."""

    def __init__(self, parent, notebook=None):
        """Initialize the Text Processing tab.

        Args:
            parent: Parent widget (notebook)
            notebook: Reference to the main notebook for tab switching
        """
        super().__init__(parent)
        self.notebook = notebook
        self._is_processing = False
        self._setup_ui()

    def _setup_ui(self):
        """Set up the tab UI with input and results sections."""
        # Main container with padding
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill='both', expand=True)

        # Configure grid weights for responsive layout
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Input Section
        self._create_input_section(main_frame)

        # Results Section (initially hidden)
        self._create_results_section(main_frame)

    def _create_input_section(self, parent):
        """Create the text input section with text area and buttons."""
        # Input frame
        input_frame = ttk.LabelFrame(parent, text="German Text Input", padding="10")
        input_frame.grid(row=0, column=0, sticky='nsew', pady=(0, 10))
        input_frame.columnconfigure(0, weight=1)
        input_frame.rowconfigure(0, weight=1)

        # Text widget with scrollbar
        text_frame = ttk.Frame(input_frame)
        text_frame.grid(row=0, column=0, sticky='nsew')
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        self.text_input = tk.Text(
            text_frame,
            wrap='word',
            height=20,
            font=('Arial', 11)
        )
        self.text_input.grid(row=0, column=0, sticky='nsew')

        # Scrollbar for text widget
        scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=self.text_input.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.text_input.configure(yscrollcommand=scrollbar.set)

        # Placeholder text
        self._placeholder_text = "Paste German text here..."
        self._insert_placeholder()

        # Bind focus events for placeholder behavior
        self.text_input.bind('<FocusIn>', self._on_focus_in)
        self.text_input.bind('<FocusOut>', self._on_focus_out)

        # Button frame
        button_frame = ttk.Frame(input_frame)
        button_frame.grid(row=1, column=0, sticky='e', pady=(10, 0))

        # Clear button
        self.clear_button = ttk.Button(
            button_frame,
            text="Clear",
            command=self._clear_text
        )
        self.clear_button.pack(side='left', padx=(0, 10))

        # Process button (primary action)
        self.process_button = ttk.Button(
            button_frame,
            text="Process Text",
            command=self._process_text,
            style='Accent.TButton'
        )
        self.process_button.pack(side='left')

        # Try to create accent style for primary button
        try:
            style = ttk.Style()
            style.configure('Accent.TButton', font=('Arial', 10, 'bold'))
        except tk.TclError:
            pass  # Style may not be supported on all platforms

    def _create_results_section(self, parent):
        """Create the results section (initially hidden)."""
        self.results_frame = ttk.LabelFrame(parent, text="Processing Results", padding="10")
        # Initially not displayed - will be shown after processing

        # Results content
        self.results_content = ttk.Frame(self.results_frame)
        self.results_content.pack(fill='both', expand=True)

        # Session ID
        session_frame = ttk.Frame(self.results_content)
        session_frame.pack(fill='x', pady=2)
        ttk.Label(session_frame, text="Session ID:", font=('Arial', 10, 'bold')).pack(side='left')
        self.session_id_label = ttk.Label(session_frame, text="")
        self.session_id_label.pack(side='left', padx=(5, 0))

        # Words processed
        processed_frame = ttk.Frame(self.results_content)
        processed_frame.pack(fill='x', pady=2)
        ttk.Label(processed_frame, text="Words processed:", font=('Arial', 10, 'bold')).pack(side='left')
        self.words_processed_label = ttk.Label(processed_frame, text="0")
        self.words_processed_label.pack(side='left', padx=(5, 0))

        # Words added to review
        added_frame = ttk.Frame(self.results_content)
        added_frame.pack(fill='x', pady=2)
        ttk.Label(added_frame, text="Words added to review:", font=('Arial', 10, 'bold')).pack(side='left')
        self.words_added_label = ttk.Label(added_frame, text="0")
        self.words_added_label.pack(side='left', padx=(5, 0))

        # Auto-translated
        translated_frame = ttk.Frame(self.results_content)
        translated_frame.pack(fill='x', pady=2)
        ttk.Label(translated_frame, text="Auto-translated:", font=('Arial', 10, 'bold')).pack(side='left')
        self.words_translated_label = ttk.Label(translated_frame, text="0")
        self.words_translated_label.pack(side='left', padx=(5, 0))

        # Success message
        self.success_frame = ttk.Frame(self.results_content)
        self.success_frame.pack(fill='x', pady=(15, 5))

        self.success_label = ttk.Label(
            self.success_frame,
            text="",
            foreground='green',
            font=('Arial', 10, 'bold')
        )
        self.success_label.pack()

        # Link to Review Queue
        self.review_link = ttk.Button(
            self.results_content,
            text="Go to Review Queue",
            command=self._go_to_review_queue
        )
        # Will be packed when results are shown

    def _insert_placeholder(self):
        """Insert placeholder text."""
        self.text_input.insert('1.0', self._placeholder_text)
        self.text_input.configure(foreground='gray')

    def _on_focus_in(self, event):
        """Handle focus in - remove placeholder if present."""
        if self.text_input.get('1.0', 'end-1c') == self._placeholder_text:
            self.text_input.delete('1.0', 'end')
            self.text_input.configure(foreground='black')

    def _on_focus_out(self, event):
        """Handle focus out - show placeholder if empty."""
        if not self.text_input.get('1.0', 'end-1c').strip():
            self._insert_placeholder()

    def _clear_text(self):
        """Clear the text input and hide results."""
        self.text_input.delete('1.0', 'end')
        self.text_input.configure(foreground='black')
        self.text_input.focus_set()

        # Hide results
        self.results_frame.grid_forget()

    def _get_text(self):
        """Get text from input, excluding placeholder."""
        text = self.text_input.get('1.0', 'end-1c').strip()
        if text == self._placeholder_text:
            return ""
        return text

    def _process_text(self):
        """Process the input text through the parser pipeline."""
        # Prevent double-click
        if self._is_processing:
            return

        # Get and validate text
        text = self._get_text()
        if not text:
            messagebox.showwarning(
                "Empty Text",
                "Please paste some German text to process."
            )
            return

        # Disable button and show processing state
        self._is_processing = True
        self.process_button.configure(state='disabled', text='Processing...')
        self.clear_button.configure(state='disabled')

        # Run processing in a separate thread to keep UI responsive
        thread = threading.Thread(target=self._run_processing, args=(text,))
        thread.daemon = True
        thread.start()

    def _run_processing(self, text):
        """Run the text processing in a background thread."""
        try:
            result = process_text_input(text)
            # Schedule UI update on main thread
            self.after(0, lambda: self._on_processing_complete(result))
        except Exception as e:
            # Schedule error handling on main thread
            self.after(0, lambda: self._on_processing_error(str(e)))

    def _on_processing_complete(self, result):
        """Handle successful processing completion."""
        # Re-enable buttons
        self._is_processing = False
        self.process_button.configure(state='normal', text='Process Text')
        self.clear_button.configure(state='normal')

        if result is None:
            messagebox.showwarning(
                "Processing Failed",
                "Could not process the text. Please check the input and try again."
            )
            return

        # Update results labels
        self.session_id_label.configure(text=result['session_id'])
        self.words_processed_label.configure(text=str(result['words_processed']))
        self.words_added_label.configure(text=str(result['words_added']))
        self.words_translated_label.configure(text=str(result['words_translated']))

        # Show success message
        if result['words_added'] > 0:
            self.success_label.configure(
                text=f"Successfully added {result['words_added']} words to review queue!",
                foreground='green'
            )
            self.review_link.pack(pady=(10, 0))
        else:
            self.success_label.configure(
                text="No new words found - all words already known!",
                foreground='blue'
            )
            self.review_link.pack_forget()

        # Show results frame
        self.results_frame.grid(row=1, column=0, sticky='nsew')

    def _on_processing_error(self, error_message):
        """Handle processing error."""
        # Re-enable buttons
        self._is_processing = False
        self.process_button.configure(state='normal', text='Process Text')
        self.clear_button.configure(state='normal')

        messagebox.showerror(
            "Processing Error",
            f"An error occurred while processing the text:\n\n{error_message}"
        )

    def _go_to_review_queue(self):
        """Switch to the Review Queue tab."""
        if self.notebook:
            # Find the Review Queue tab index
            for i in range(self.notebook.index('end')):
                if 'Review' in self.notebook.tab(i, 'text'):
                    self.notebook.select(i)
                    break
