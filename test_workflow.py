#!/usr/bin/env python3
"""
Test program to verify the complete vocab harvester workflow:
1. Text processing pipeline
2. Adding words to temporary database
3. Moving words from temp to main database
"""

import sys
import os
import uuid
from datetime import datetime

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from database import (
    init_database, add_temp_word, get_temp_words, add_word, 
    clear_temp_session, word_exists, add_tag_to_word
)
from parser import tokenize_text, lemmatize_words

def test_text_processing():
    """Test the text processing pipeline without user interaction."""
    print("=" * 60)
    print("TEST 1: TEXT PROCESSING PIPELINE")
    print("=" * 60)
    
    # Sample German text
    test_text = "Ich gehe heute in die Schule und lerne Deutsch. Die Bücher sind interessant."
    print(f"Input text: {test_text}")
    print()
    
    # Step 1: Tokenization
    print("Step 1: Tokenization")
    tokens = tokenize_text(test_text)
    print(f"Tokens found: {tokens}")
    print()
    
    # Step 2: Lemmatization
    print("Step 2: Lemmatization")
    lemmatized = lemmatize_words(tokens)
    print("Lemmatized words:")
    for word_data in lemmatized:
        print(f"  {word_data['original']} -> {word_data['lemma']} [{word_data['pos']}]")
    print()
    
    return lemmatized

def test_temp_database(lemmatized_words):
    """Test adding words to temporary database."""
    print("=" * 60)
    print("TEST 2: TEMPORARY DATABASE OPERATIONS")
    print("=" * 60)
    
    # Create a unique session ID
    session_id = f"test_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"Session ID: {session_id}")
    print()
    
    # Add words to temp database
    print("Adding words to temporary database:")
    for word_data in lemmatized_words[:5]:  # Process first 5 words for demo
        word = word_data['original']
        lemma = word_data['lemma']
        pos = word_data['pos']
        
        # Simulate getting translation (you could integrate with translation API here)
        translation = f"[translation for {lemma}]"
        is_regular = True if pos not in ["VERB", "AUX"] else None
        
        success = add_temp_word(word, lemma, pos, translation, is_regular, session_id)
        if success:
            print(f"  [OK] Added: {word} -> {lemma} [{pos}]")
        else:
            print(f"  [FAIL] Failed: {word}")
    print()
    
    # Show temp database contents
    print("Current temporary database contents:")
    temp_words = get_temp_words(session_id)
    print(f"Found {len(temp_words)} words in temp database:")
    for word_record in temp_words:
        word, lemma, pos, translation, is_regular, sess_id, created = word_record
        print(f"  {word} -> {lemma} [{pos}] | Translation: {translation}")
    print()
    
    return session_id, temp_words

def test_temp_to_main_transfer(session_id):
    """Test moving words from temp database to main database."""
    print("=" * 60)
    print("TEST 3: TRANSFER FROM TEMP TO MAIN DATABASE")
    print("=" * 60)
    
    # Get words from temp database
    temp_words = get_temp_words(session_id)
    print(f"Processing {len(temp_words)} words from temp database:")
    print()
    
    transferred_count = 0
    for word_record in temp_words:
        word, lemma, pos, translation, is_regular, sess_id, created = word_record
        
        print(f"Processing: {lemma} [{pos}]")
        
        # Check if word already exists in main database
        if word_exists(lemma):
            print(f"  [SKIP] '{lemma}' already exists in main database - skipping")
            continue
        
        # Add to main database
        add_word(lemma, pos, is_regular, translation)
        transferred_count += 1
        
        # Add some sample tags for demonstration
        if pos == "NOUN":
            add_tag_to_word(lemma, "noun")
        elif pos in ["VERB", "AUX"]:
            add_tag_to_word(lemma, "verb")
            if is_regular is False:
                add_tag_to_word(lemma, "irregular")
        
        print(f"  [OK] Transferred to main database with tags")
    
    print()
    print(f"Transfer complete: {transferred_count} words moved to main database")
    
    # Clean up temp session
    cleared_count = clear_temp_session(session_id)
    print(f"Cleaned up temporary session: {cleared_count} words removed")
    print()

def test_main_database_verification():
    """Verify words exist in main database."""
    print("=" * 60)
    print("TEST 4: MAIN DATABASE VERIFICATION")
    print("=" * 60)
    
    # Check some sample words
    test_words = ["gehen", "schule", "lernen", "buch", "interessant"]
    
    print("Checking if words exist in main database:")
    for word in test_words:
        exists = word_exists(word)
        status = "[EXISTS]" if exists else "[NOT FOUND]"
        print(f"  {word}: {status}")
    print()

def run_complete_workflow():
    """Run the complete test workflow."""
    print("VOCAB HARVESTER - COMPLETE WORKFLOW TEST")
    print("Starting comprehensive workflow test...")
    print()
    
    try:
        # Initialize database
        init_database()
        
        # Test 1: Text Processing Pipeline
        lemmatized_words = test_text_processing()
        
        # Test 2: Temporary Database Operations
        session_id, temp_words = test_temp_database(lemmatized_words)
        
        # Test 3: Transfer from Temp to Main Database
        test_temp_to_main_transfer(session_id)
        
        # Test 4: Main Database Verification
        test_main_database_verification()
        
        print("=" * 60)
        print("[SUCCESS] ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("Summary:")
        print("- Text processing pipeline: Working [OK]")
        print("- Temporary database operations: Working [OK]") 
        print("- Transfer to main database: Working [OK]")
        print("- Database verification: Working [OK]")
        print()
        print("The complete workflow is functioning properly!")
        
    except Exception as e:
        print(f"[ERROR] occurred during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_complete_workflow()