"""Entry point for the Vocab Harvester UI application."""

import sys
import os
import tkinter as tk

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import VocabHarvesterApp


if __name__ == "__main__":
    root = tk.Tk()
    app = VocabHarvesterApp(root)
    app.run()
