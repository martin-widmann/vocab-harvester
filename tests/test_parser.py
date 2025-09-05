#!/usr/bin/env python3
"""Test script to process the German text directly"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from parser import process_text_input

def test_text_processing():
    test_text = """Fort, fort, will ich laufen, aber sie fassen mich bald an der Jacke. "Ich bin doch schon gefangen! Ich werde ja doch gefangen!" Ich laufe, ich laufe, doch sie fassen mich an der Jacke"""
    
    print("Testing German text processing...")
    print(f"Input text: {test_text}")
    print("-" * 50)
    
    try:
        # Process with non-interactive mode (no tags added automatically)
        process_text_input(test_text, interactive=False)
        print("Test completed successfully!")
    except Exception as e:
        print(f"Error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_text_processing()