"""Test the UI structure."""

import sys
import os
import tkinter as tk

# Add src/ui to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'ui'))

from app import VocabHarvesterApp


def test_ui_initialization():
    """Test that the UI initializes without errors."""
    root = tk.Tk()
    app = VocabHarvesterApp(root)

    # Update the window to apply geometry settings
    root.update_idletasks()

    # Verify the application has been created
    assert app is not None
    assert app.root == root

    # Verify window properties
    assert root.title() == "Vocab Harvester"
    # Verify the requested size was set (actual geometry might differ slightly)
    geometry = root.geometry()
    assert geometry.startswith("900x600") or "900x600" in geometry

    # Verify notebook exists
    assert app.notebook is not None

    # Verify tabs exist
    assert app.text_processing_tab is not None
    assert app.vocabulary_tab is not None
    assert app.review_queue_tab is not None

    # Verify notebook has 3 tabs
    assert app.notebook.index("end") == 3

    # Clean up
    root.destroy()

    print("All UI structure tests passed!")


if __name__ == "__main__":
    test_ui_initialization()
