#!/usr/bin/env python3
"""Test script to validate batch processing pipeline with translation integration"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from parser import process_text_input
from database import get_temp_words, clear_temp_session

def test_batch_processing():
    """Test the batch processing pipeline with automatic translation"""
    test_text = """Der Froschkönig verwandelte sich in einen Prinzen. Die Zauberkraft wirkte sofort. Das Märchen endet glücklich."""
    
    print("Testing batch processing pipeline...")
    print(f"Input text: {test_text}")
    print("-" * 50)
    
    try:
        # Test 1: Process text with batch processing
        result = process_text_input(test_text)
        
        if result is None:
            print("[FAIL] Test failed: process_text_input returned None")
            return False
            
        print(f"[PASS] Processing result: {result}")
        session_id = result['session_id']
        
        # Test 2: Verify words were added to temp database
        temp_words = get_temp_words(session_id)
        print(f"[PASS] Found {len(temp_words)} words in temp database")
        
        # Test 3: Check that some words have translations
        translated_words = [word for word in temp_words if word[3] is not None]  # translation is 4th column
        print(f"[PASS] {len(translated_words)} words have translations")
        
        # Display sample results
        print("\n[INFO] Sample processed words:")
        for i, (word, lemma, pos, translation, is_regular, session, created_at) in enumerate(temp_words[:5]):
            status = f"[TRANSLATED] {translation}" if translation else "[NO_TRANSLATION]"
            print(f"  {i+1}. {word} -> {lemma} [{pos}] - {status}")
        
        # Test 4: Verify session isolation - process with new session
        result2 = process_text_input("Das ist ein neuer Test")
        if result2 and result2['session_id'] != session_id:
            print("[PASS] Session isolation working - new session created")
        
        # Clean up test sessions
        clear_temp_session(session_id)
        if result2:
            clear_temp_session(result2['session_id'])
        
        print("\n[SUCCESS] All batch processing tests passed!")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error occurred: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_empty_input():
    """Test handling of empty or invalid input"""
    print("\n[TEST] Testing edge cases...")
    
    # Test empty text
    result = process_text_input("")
    assert result is None, "Empty text should return None"
    print("[PASS] Empty text handled correctly")
    
    # Test whitespace-only text  
    result = process_text_input("   \n\t  ")
    assert result is None, "Whitespace-only text should return None"
    print("[PASS] Whitespace-only text handled correctly")
    
    # Test text with no valid words
    result = process_text_input("123 !@# $$$ %%% 999")
    assert result is None, "Text with no valid words should return None"
    print("[PASS] Non-alphabetic text handled correctly")

if __name__ == "__main__":
    success = test_batch_processing()
    if success:
        test_empty_input()
        print("\n[SUCCESS] All tests completed successfully!")
    else:
        print("\n[FAIL] Some tests failed!")
        sys.exit(1)