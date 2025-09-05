#!/usr/bin/env python3
"""Test script to demonstrate manual tagging per word"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from database import add_tag_to_word, get_word_tags, get_words_with_tag, list_all_tags
from parser import process_text_input

def test_manual_tagging():
    print("Testing manual tagging system...")
    print("=" * 50)
    
    # First, let's add some words without tags (non-interactive)
    test_text = "Das ist schwierig"
    print(f"Processing text non-interactively: {test_text}")
    process_text_input(test_text, interactive=False)
    
    print("\n" + "-" * 50)
    print("Now manually adding tags to specific words:")
    
    # Manually add tags to specific words
    add_tag_to_word("schwierig", "difficult")
    add_tag_to_word("schwierig", "adjective") 
    add_tag_to_word("das", "basic")
    add_tag_to_word("sein", "basic")
    
    print("\n" + "-" * 50)
    print("RESULTS:")
    
    # Show all tags
    print("All available tags:")
    tags = list_all_tags()
    for tag_name, description in tags:
        print(f"  • {tag_name}: {description or 'No description'}")
    
    print("\nWords with their tags:")
    # Show words by tag
    for tag_name, _ in tags:
        words = get_words_with_tag(tag_name)
        if words:
            print(f"\nTag '{tag_name}':")
            for word, pos, is_regular in words:
                print(f"  • {word} ({pos})")
    
    print("\n" + "-" * 50)
    print("Tags for specific word 'schwierig':")
    word_tags = get_word_tags("schwierig")
    for tag_name, description in word_tags:
        print(f"  • {tag_name}: {description or 'No description'}")

if __name__ == "__main__":
    test_manual_tagging()