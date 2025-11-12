#!/usr/bin/env python3
"""
Tests for difficulty field functionality in vocabulary database.
Issue #12: Add difficulty field to vocabulary database and review workflow
"""

import sys
import os
import sqlite3
import pytest

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database import (
    init_database, connect_db, add_temp_word, approve_word,
    word_exists, DB_FILE, TABLE_NAME, clear_session
)


@pytest.fixture
def test_db():
    """Set up and tear down test database."""
    # Backup existing database if it exists
    backup_path = None
    if os.path.exists(DB_FILE):
        backup_path = DB_FILE + ".backup"
        if os.path.exists(backup_path):
            os.remove(backup_path)
        os.rename(DB_FILE, backup_path)

    # Initialize fresh database
    init_database()

    yield

    # Clean up
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

    # Restore backup if it existed
    if backup_path and os.path.exists(backup_path):
        os.rename(backup_path, DB_FILE)


def test_difficulty_column_exists(test_db):
    """Test that difficulty column exists in vocab table."""
    conn = connect_db()
    cursor = conn.cursor()

    # Get table info
    cursor.execute(f"PRAGMA table_info({TABLE_NAME})")
    columns = cursor.fetchall()

    # Check if difficulty column exists
    column_names = [col[1] for col in columns]
    assert 'difficulty' in column_names, "Difficulty column should exist in vocab table"

    # Check difficulty column type
    difficulty_col = [col for col in columns if col[1] == 'difficulty'][0]
    assert 'INTEGER' in difficulty_col[2].upper(), "Difficulty column should be INTEGER type"

    conn.close()


def test_difficulty_default_value(test_db):
    """Test that difficulty has default value of 3."""
    conn = connect_db()
    cursor = conn.cursor()

    # Get table info
    cursor.execute(f"PRAGMA table_info({TABLE_NAME})")
    columns = cursor.fetchall()

    # Find difficulty column and check default value
    difficulty_col = [col for col in columns if col[1] == 'difficulty'][0]
    default_value = difficulty_col[4]  # Column index 4 is the default value

    assert default_value == '3', "Difficulty default value should be 3 (medium)"

    conn.close()


def test_approve_word_with_difficulty(test_db):
    """Test approving a word with specific difficulty level."""
    session_id = "test_session_difficulty"

    # Add a test word to temp database
    add_temp_word("Haus", "haus", "NOUN", "house", True, session_id)

    # Approve word with difficulty 4 (hard)
    result = approve_word("haus", session_id, difficulty=4)
    assert result is True, "Word should be approved successfully"

    # Verify word exists in main database with correct difficulty
    assert word_exists("haus"), "Word should exist in main database"

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(f"SELECT difficulty FROM {TABLE_NAME} WHERE word = ?", ("haus",))
    difficulty = cursor.fetchone()[0]
    conn.close()

    assert difficulty == 4, "Word should have difficulty level 4"

    # Clean up
    clear_session(session_id)


def test_approve_word_default_difficulty(test_db):
    """Test approving a word with default difficulty (no parameter)."""
    session_id = "test_session_default"

    # Add a test word to temp database
    add_temp_word("Katze", "katze", "NOUN", "cat", True, session_id)

    # Approve word without specifying difficulty (should use default=3)
    result = approve_word("katze", session_id)
    assert result is True, "Word should be approved successfully"

    # Verify word has default difficulty of 3
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(f"SELECT difficulty FROM {TABLE_NAME} WHERE word = ?", ("katze",))
    difficulty = cursor.fetchone()[0]
    conn.close()

    assert difficulty == 3, "Word should have default difficulty level 3"

    # Clean up
    clear_session(session_id)


def test_all_difficulty_levels(test_db):
    """Test all difficulty levels (0-4)."""
    session_id = "test_session_levels"

    test_words = [
        ("und", "und", "CCONJ", "and", None, 0, "known"),
        ("Hund", "hund", "NOUN", "dog", True, 1, "supereasy"),
        ("trotzdem", "trotzdem", "ADV", "nevertheless", None, 2, "easy"),
        ("Werkzeug", "werkzeug", "NOUN", "tool", True, 3, "medium"),
        ("verweilen", "verweilen", "VERB", "linger", False, 4, "hard"),
    ]

    for word, lemma, pos, translation, is_regular, difficulty, level_name in test_words:
        # Add to temp database
        add_temp_word(word, lemma, pos, translation, is_regular, session_id)

        # Approve with specific difficulty
        result = approve_word(lemma, session_id, difficulty=difficulty)
        assert result is True, f"Word '{lemma}' should be approved"

        # Verify difficulty in database
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(f"SELECT difficulty FROM {TABLE_NAME} WHERE word = ?", (lemma,))
        stored_difficulty = cursor.fetchone()[0]
        conn.close()

        assert stored_difficulty == difficulty, \
            f"Word '{lemma}' should have difficulty {difficulty} ({level_name})"

    # Clean up
    clear_session(session_id)


def test_difficulty_with_tags(test_db):
    """Test that difficulty works alongside tags."""
    session_id = "test_session_tags"

    # Add a test word to temp database
    add_temp_word("Herzinfarkt", "herzinfarkt", "NOUN", "heart attack", True, session_id)

    # Approve word with both difficulty and tags
    result = approve_word("herzinfarkt", session_id, difficulty=4, tags=["medical", "important"])
    assert result is True, "Word should be approved successfully"

    # Verify word has correct difficulty
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(f"SELECT difficulty FROM {TABLE_NAME} WHERE word = ?", ("herzinfarkt",))
    difficulty = cursor.fetchone()[0]

    # Verify tags exist
    cursor.execute("""
        SELECT t.tag_name FROM tags t
        JOIN word_tags wt ON t.tag_id = wt.tag_id
        WHERE wt.word = ?
    """, ("herzinfarkt",))
    tags = [row[0] for row in cursor.fetchall()]

    conn.close()

    assert difficulty == 4, "Word should have difficulty 4"
    assert "medical" in tags, "Word should have 'medical' tag"
    assert "important" in tags, "Word should have 'important' tag"

    # Clean up
    clear_session(session_id)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
