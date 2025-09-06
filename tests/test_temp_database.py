#!/usr/bin/env python3
"""
Tests for temporary database functionality (Issue #2)
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import uuid
from database import (
    add_temp_word, get_temp_words, remove_temp_word, 
    clear_temp_session, temp_word_exists, connect_db
)

def test_add_temp_word():
    """Test adding words to temporary database."""
    session_id = f"test_{uuid.uuid4().hex[:8]}"
    
    # Test adding a word
    result = add_temp_word(
        word='testword', 
        lemma='testword', 
        pos='NOUN', 
        translation='test translation', 
        is_regular=True, 
        session_id=session_id
    )
    
    assert result is True, "add_temp_word should return True on success"
    
    # Verify word exists
    assert temp_word_exists('testword', session_id), "Word should exist in temp database"
    
    # Clean up
    clear_temp_session(session_id)

def test_get_temp_words():
    """Test retrieving words from temporary database."""
    session_id = f"test_{uuid.uuid4().hex[:8]}"
    
    # Add test words
    add_temp_word('word1', 'word1', 'NOUN', 'translation1', True, session_id)
    add_temp_word('word2', 'word2', 'VERB', 'translation2', False, session_id)
    
    # Get words for session
    words = get_temp_words(session_id)
    assert len(words) == 2, "Should retrieve 2 words for session"
    
    # Check word data structure
    word_data = words[0]
    assert len(word_data) == 7, "Word data should have 7 fields"
    assert word_data[0] in ['word1', 'word2'], "Word field should match"
    assert word_data[1] in ['word1', 'word2'], "Lemma field should match"
    assert word_data[5] == session_id, "Session ID should match"
    
    # Test getting all words (no session filter)
    all_words = get_temp_words()
    assert len(all_words) >= 2, "Should retrieve at least our test words"
    
    # Clean up
    clear_temp_session(session_id)

def test_remove_temp_word():
    """Test removing specific words from temporary database."""
    session_id = f"test_{uuid.uuid4().hex[:8]}"
    
    # Add test word
    add_temp_word('removetest', 'removetest', 'ADJ', 'remove translation', True, session_id)
    
    # Verify it exists
    assert temp_word_exists('removetest', session_id), "Word should exist before removal"
    
    # Remove the word
    result = remove_temp_word('removetest', session_id)
    assert result is True, "remove_temp_word should return True on success"
    
    # Verify it's gone
    assert not temp_word_exists('removetest', session_id), "Word should not exist after removal"
    
    # Test removing non-existent word
    result = remove_temp_word('nonexistent', session_id)
    assert result is False, "remove_temp_word should return False for non-existent word"

def test_clear_temp_session():
    """Test clearing entire sessions from temporary database."""
    session_id = f"test_{uuid.uuid4().hex[:8]}"
    
    # Add multiple test words
    add_temp_word('clear1', 'clear1', 'NOUN', 'translation1', True, session_id)
    add_temp_word('clear2', 'clear2', 'VERB', 'translation2', False, session_id)
    add_temp_word('clear3', 'clear3', 'ADJ', 'translation3', True, session_id)
    
    # Verify words exist
    words = get_temp_words(session_id)
    assert len(words) == 3, "Should have 3 words before clearing"
    
    # Clear session
    count = clear_temp_session(session_id)
    assert count == 3, "Should return count of cleared words"
    
    # Verify session is empty
    words = get_temp_words(session_id)
    assert len(words) == 0, "Session should be empty after clearing"

def test_temp_word_exists():
    """Test checking word existence in temporary database."""
    session_id = f"test_{uuid.uuid4().hex[:8]}"
    
    # Test non-existent word
    assert not temp_word_exists('nonexistent', session_id), "Non-existent word should return False"
    
    # Add word and test existence
    add_temp_word('existstest', 'existstest', 'NOUN', 'test translation', True, session_id)
    assert temp_word_exists('existstest', session_id), "Existing word should return True"
    
    # Test word doesn't exist in different session
    other_session = f"other_{uuid.uuid4().hex[:8]}"
    assert not temp_word_exists('existstest', other_session), "Word should not exist in different session"
    
    # Clean up
    clear_temp_session(session_id)

def test_session_isolation():
    """Test that sessions are properly isolated."""
    session1 = f"test1_{uuid.uuid4().hex[:8]}"
    session2 = f"test2_{uuid.uuid4().hex[:8]}"
    
    # Add words to different sessions
    add_temp_word('session1word', 'session1word', 'NOUN', 'translation1', True, session1)
    add_temp_word('session2word', 'session2word', 'VERB', 'translation2', False, session2)
    
    # Check session isolation
    words1 = get_temp_words(session1)
    words2 = get_temp_words(session2)
    
    assert len(words1) == 1, "Session 1 should have 1 word"
    assert len(words2) == 1, "Session 2 should have 1 word"
    assert words1[0][0] == 'session1word', "Session 1 should contain session1word"
    assert words2[0][0] == 'session2word', "Session 2 should contain session2word"
    
    # Clean up
    clear_temp_session(session1)
    clear_temp_session(session2)

def test_temp_database_schema():
    """Test that temporary database schema is correctly created."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(temp_vocab)")
    columns = cursor.fetchall()
    conn.close()
    
    column_names = [col[1] for col in columns]
    expected_columns = ['word', 'lemma', 'pos', 'translation', 'is_regular', 'session_id', 'created_at']
    
    for expected_col in expected_columns:
        assert expected_col in column_names, f"Column '{expected_col}' should exist in temp_vocab table"

if __name__ == "__main__":
    test_add_temp_word()
    test_get_temp_words()
    test_remove_temp_word()
    test_clear_temp_session()
    test_temp_word_exists()
    test_session_isolation()
    test_temp_database_schema()
    print("All temporary database tests passed!")