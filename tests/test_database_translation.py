#!/usr/bin/env python3
"""
Tests for database translation functionality (Issue #1)
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import sqlite3
import tempfile
from database import add_word, word_exists, connect_db, DB_FILE

def test_add_word_with_translation():
    """Test that add_word works with translation parameter."""
    # Clean test by removing any existing test words
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vocab WHERE word = 'testword'")
    conn.commit()
    conn.close()
    
    # Test adding word with translation
    add_word('testword', 'NOUN', True, 'test translation')
    
    # Verify word was added with translation
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT word, pos, is_regular, translation FROM vocab WHERE word = 'testword'")
    result = cursor.fetchone()
    conn.close()
    
    assert result is not None, "Word was not added to database"
    assert result[0] == 'testword', "Word field incorrect"
    assert result[1] == 'NOUN', "POS field incorrect"
    assert result[2] == 1, "is_regular field incorrect"  # SQLite stores boolean as integer
    assert result[3] == 'test translation', "Translation field incorrect"

def test_add_word_without_translation():
    """Test that add_word works without translation parameter (backward compatibility)."""
    # Clean test by removing any existing test words
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vocab WHERE word = 'testword2'")
    conn.commit()
    conn.close()
    
    # Test adding word without translation (should default to None)
    add_word('testword2', 'VERB', False)
    
    # Verify word was added with null translation
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT word, pos, is_regular, translation FROM vocab WHERE word = 'testword2'")
    result = cursor.fetchone()
    conn.close()
    
    assert result is not None, "Word was not added to database"
    assert result[0] == 'testword2', "Word field incorrect"
    assert result[1] == 'VERB', "POS field incorrect"
    assert result[2] == 0, "is_regular field incorrect"  # SQLite stores boolean as integer
    assert result[3] is None, "Translation field should be None"

def test_database_schema_has_translation_column():
    """Test that the database schema includes the translation column."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(vocab)")
    columns = cursor.fetchall()
    conn.close()
    
    column_names = [col[1] for col in columns]
    assert 'translation' in column_names, "Translation column not found in vocab table schema"

if __name__ == "__main__":
    test_add_word_with_translation()
    test_add_word_without_translation()
    test_database_schema_has_translation_column()
    print("All database translation tests passed!")