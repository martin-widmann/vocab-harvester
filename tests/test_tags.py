#!/usr/bin/env python3
"""Test script to demonstrate the new tagging system"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from parser import process_text_input
from database import (add_tag_to_word, get_word_tags, get_words_with_tag, 
                     list_all_tags, create_tag)

def test_tagging_system():
    print("Testing new tagging system...")
    print("=" * 40)
    
    # Test text processing with tags
    test_text = "Das ist ein medizinischer Fachbegriff für schwierige Konzepte."
    print(f"Processing: {test_text}")
    print("-" * 40)
    
    # Process text (no automatic tags in non-interactive mode)
    process_text_input(test_text, interactive=False)
    
    print("\n" + "=" * 40)
    print("Testing tag operations...")
    
    # Create some additional tags
    create_tag("difficult", "Words that are hard to learn")
    create_tag("formal", "Formal language words")
    
    # Add more tags to specific words
    add_tag_to_word("medizinisch", "difficult")
    add_tag_to_word("fachbegriff", "formal")
    add_tag_to_word("konzept", "technical")
    
    print("\n" + "-" * 40)
    print("TAGGING RESULTS:")
    print("-" * 40)
    
    # Show all available tags
    print("All available tags:")
    tags = list_all_tags()
    for tag_name, description in tags:
        print(f"  • {tag_name}: {description or 'No description'}")
    
    print("\nWords with tags:")
    for tag_name, _ in tags:
        words = get_words_with_tag(tag_name)
        if words:
            print(f"\nTag '{tag_name}':")
            for word, pos, is_regular in words:
                word_tags = get_word_tags(word)
                all_tags = [t[0] for t in word_tags]
                print(f"  • {word} ({pos}) - Tags: {', '.join(all_tags)}")

if __name__ == "__main__":
    test_tagging_system()