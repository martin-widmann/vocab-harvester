import sqlite3
import os

# Database file path
DB_FILE = "C:/Users/marti/Projects-2025/vocab-harvester/database/vocab.db"
TABLE_NAME = "vocab"

# Ensure the database directory exists
os.makedirs("database", exist_ok=True)

def connect_db():
    """Connect to SQLite database and return the connection."""
    return sqlite3.connect(DB_FILE)

def init_database():
    """Initialize the SQLite database with vocabulary and tagging system."""
    conn = connect_db()
    cursor = conn.cursor()
    
    # Create main vocabulary table (simplified schema)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            word TEXT PRIMARY KEY,
            pos TEXT,
            is_regular BOOLEAN,
            translation TEXT,
            difficulty INTEGER DEFAULT 3
        )
    """)
    
    # Create tags table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag_name TEXT UNIQUE NOT NULL,
            description TEXT
        )
    """)
    
    # Create word_tags junction table for many-to-many relationship
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS word_tags (
            word TEXT NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (word, tag_id),
            FOREIGN KEY (word) REFERENCES vocab (word) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags (tag_id) ON DELETE CASCADE
        )
    """)
    
    # Create temporary processing database table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS temp_vocab (
            word TEXT NOT NULL,
            lemma TEXT NOT NULL,
            pos TEXT,
            translation TEXT,
            is_regular BOOLEAN,
            session_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (word, session_id)
        )
    """)
    
    conn.commit()
    conn.close()

def word_exists(word):
    """Check if a word already exists in the database."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(f"SELECT word FROM {TABLE_NAME} WHERE word = ?", (word,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def add_word(word, pos, is_regular, translation=None, difficulty=3):
    """Insert a new word into the database safely."""
    if word_exists(word):
        print(f"'{word}' already exists in the database. Skipping.")
        return

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                INSERT INTO {TABLE_NAME} (word, pos, is_regular, translation, difficulty)
                VALUES (?, ?, ?, ?, ?)
            """, (word, pos, is_regular, translation, difficulty))
            conn.commit()
            print(f"Added '{word}' to the database.")
    except sqlite3.Error as e:
        print(f"Database error: {e}")

# Tag management functions
def create_tag(tag_name, description=None):
    """Create a new tag."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tags (tag_name, description)
                VALUES (?, ?)
            """, (tag_name, description))
            conn.commit()
            print(f"Created tag '{tag_name}'")
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        print(f"Tag '{tag_name}' already exists")
        return get_tag_id(tag_name)
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None

def get_tag_id(tag_name):
    """Get tag ID by name."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT tag_id FROM tags WHERE tag_name = ?", (tag_name,))
            result = cursor.fetchone()
            return result[0] if result else None
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None

def add_tag_to_word(word, tag_name):
    """Add a tag to a word."""
    if not word_exists(word):
        print(f"Word '{word}' doesn't exist in database")
        return False
    
    tag_id = get_tag_id(tag_name)
    if not tag_id:
        # Create tag if it doesn't exist
        tag_id = create_tag(tag_name)
        if not tag_id:
            return False
    
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO word_tags (word, tag_id)
                VALUES (?, ?)
            """, (word, tag_id))
            conn.commit()
            if cursor.rowcount > 0:
                print(f"Added tag '{tag_name}' to word '{word}'")
            else:
                print(f"Word '{word}' already has tag '{tag_name}'")
            return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False

def remove_tag_from_word(word, tag_name):
    """Remove a tag from a word."""
    tag_id = get_tag_id(tag_name)
    if not tag_id:
        print(f"Tag '{tag_name}' doesn't exist")
        return False
    
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM word_tags WHERE word = ? AND tag_id = ?
            """, (word, tag_id))
            conn.commit()
            if cursor.rowcount > 0:
                print(f"Removed tag '{tag_name}' from word '{word}'")
            else:
                print(f"Word '{word}' doesn't have tag '{tag_name}'")
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False

def get_word_tags(word):
    """Get all tags for a word."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.tag_name, t.description
                FROM tags t
                JOIN word_tags wt ON t.tag_id = wt.tag_id
                WHERE wt.word = ?
            """, (word,))
            return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []

def get_words_with_tag(tag_name):
    """Get all words that have a specific tag."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT v.word, v.pos, v.is_regular
                FROM vocab v
                JOIN word_tags wt ON v.word = wt.word
                JOIN tags t ON wt.tag_id = t.tag_id
                WHERE t.tag_name = ?
            """, (tag_name,))
            return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []

def list_all_tags():
    """List all available tags."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT tag_name, description FROM tags ORDER BY tag_name")
            return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []

def delete_tag(tag_name):
    """Delete a tag and all its associations."""
    tag_id = get_tag_id(tag_name)
    if not tag_id:
        print(f"Tag '{tag_name}' doesn't exist")
        return False
    
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # Delete associations first (will happen automatically due to CASCADE)
            cursor.execute("DELETE FROM tags WHERE tag_id = ?", (tag_id,))
            conn.commit()
            print(f"Deleted tag '{tag_name}' and all its associations")
            return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False

# Temporary database management functions
def add_temp_word(word, lemma, pos, translation, is_regular, session_id):
    """Add a word to temporary processing database."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO temp_vocab
                (word, lemma, pos, translation, is_regular, session_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (word, lemma, pos, translation, is_regular, session_id))
            conn.commit()
            return True
    except sqlite3.Error as e:
        print(f"Database error adding temp word: {e}")
        return False


def get_temp_words(session_id=None):
    """Get all words from temporary database, optionally filtered by session."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            if session_id:
                cursor.execute("""
                    SELECT word, lemma, pos, translation, is_regular, session_id, created_at
                    FROM temp_vocab WHERE session_id = ?
                    ORDER BY created_at
                """, (session_id,))
            else:
                cursor.execute("""
                    SELECT word, lemma, pos, translation, is_regular, session_id, created_at
                    FROM temp_vocab ORDER BY created_at
                """)
            return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Database error getting temp words: {e}")
        return []


def remove_temp_word(word, session_id):
    """Remove a specific word from temporary database."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM temp_vocab WHERE word = ? AND session_id = ?
            """, (word, session_id))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"Database error removing temp word: {e}")
        return False


def clear_temp_session(session_id):
    """Remove all words from a specific session."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM temp_vocab WHERE session_id = ?
            """, (session_id,))
            conn.commit()
            print(f"Cleared session '{session_id}' - {cursor.rowcount} words removed")
            return cursor.rowcount
    except sqlite3.Error as e:
        print(f"Database error clearing session: {e}")
        return 0


def temp_word_exists(word, session_id):
    """Check if a word exists in temporary database for a specific session."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT word FROM temp_vocab WHERE word = ? AND session_id = ?
            """, (word, session_id))
            return cursor.fetchone() is not None
    except sqlite3.Error as e:
        print(f"Database error checking temp word existence: {e}")
        return False


# Word approval workflow functions
def approve_word(lemma, session_id, difficulty=3, tags=None):
    """
    Approve a word from temporary database and move it to main vocabulary.

    Args:
        lemma: The lemmatized word to approve
        session_id: The session ID where the word is stored
        difficulty: Difficulty level (0=known, 1=supereasy, 2=easy, 3=medium, 4=hard)
        tags: Optional list of tag names to assign to the word

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            # Find the word in temp database
            cursor.execute("""
                SELECT word, lemma, pos, translation, is_regular
                FROM temp_vocab
                WHERE lemma = ? AND session_id = ?
                LIMIT 1
            """, (lemma, session_id))

            temp_word = cursor.fetchone()
            if not temp_word:
                print(f"Word '{lemma}' not found in session '{session_id}'")
                return False

            word, lemma_found, pos, translation, is_regular = temp_word

            # Check if word already exists in main database
            cursor.execute(f"SELECT word FROM {TABLE_NAME} WHERE word = ?", (lemma_found,))
            if cursor.fetchone():
                print(f"Word '{lemma_found}' already exists in main database")
                # Remove from temp even if already exists
                cursor.execute("""
                    DELETE FROM temp_vocab WHERE lemma = ? AND session_id = ?
                """, (lemma, session_id))
                conn.commit()
                return False

            # Insert word into main database
            cursor.execute(f"""
                INSERT INTO {TABLE_NAME} (word, pos, is_regular, translation, difficulty)
                VALUES (?, ?, ?, ?, ?)
            """, (lemma_found, pos, is_regular, translation, difficulty))

            # Add tags if provided
            if tags:
                for tag_name in tags:
                    # Get or create tag
                    cursor.execute("SELECT tag_id FROM tags WHERE tag_name = ?", (tag_name,))
                    result = cursor.fetchone()

                    if result:
                        tag_id = result[0]
                    else:
                        # Create new tag
                        cursor.execute("""
                            INSERT INTO tags (tag_name, description)
                            VALUES (?, NULL)
                        """, (tag_name,))
                        tag_id = cursor.lastrowid

                    # Add tag association
                    cursor.execute("""
                        INSERT OR IGNORE INTO word_tags (word, tag_id)
                        VALUES (?, ?)
                    """, (lemma_found, tag_id))

            # Remove from temporary database
            cursor.execute("""
                DELETE FROM temp_vocab WHERE lemma = ? AND session_id = ?
            """, (lemma, session_id))

            conn.commit()
            print(f"Approved word '{lemma_found}' and moved to main database")
            return True

    except sqlite3.Error as e:
        print(f"Database error approving word: {e}")
        return False


def prompt_difficulty():
    """
    Prompt user for word difficulty level.

    Returns:
        Integer 0-4 representing difficulty:
        0=known, 1=supereasy, 2=easy, 3=medium, 4=hard
    """
    print("\nDifficulty: 0=known, 1=supereasy, 2=easy, 3=medium, 4=hard")

    while True:
        try:
            choice = input("Select [0-4]: ").strip()
            difficulty = int(choice)

            if 0 <= difficulty <= 4:
                return difficulty
            else:
                print("Please enter 0-4")
        except ValueError:
            print("Invalid input")


def reject_word(lemma, session_id):
    """
    Reject a word and remove it from temporary database.

    Args:
        lemma: The lemmatized word to reject
        session_id: The session ID where the word is stored

    Returns:
        bool: True if word was removed, False otherwise
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM temp_vocab WHERE lemma = ? AND session_id = ?
            """, (lemma, session_id))
            conn.commit()

            if cursor.rowcount > 0:
                print(f"Rejected word '{lemma}' from session '{session_id}'")
                return True
            else:
                print(f"Word '{lemma}' not found in session '{session_id}'")
                return False

    except sqlite3.Error as e:
        print(f"Database error rejecting word: {e}")
        return False


def get_pending_words(session_id=None):
    """
    Get all words awaiting approval from temporary database.

    Args:
        session_id: Optional session ID to filter by specific session

    Returns:
        list: List of tuples (word, lemma, pos, translation, is_regular, session_id, created_at)
    """
    # This is an alias for get_temp_words for semantic clarity
    return get_temp_words(session_id)


def clear_session(session_id):
    """
    Clear all words from a processing session.

    Args:
        session_id: The session ID to clear

    Returns:
        int: Number of words removed
    """
    # This is an alias for clear_temp_session for semantic clarity
    return clear_temp_session(session_id)


# UI Query Functions
def get_all_words(filters=None, search_term=None):
    """
    Get all words from main vocabulary table with optional filtering.

    Args:
        filters: Optional dict with filter criteria (e.g., {'difficulty': 3})
        search_term: Optional string to search in word or translation

    Returns:
        list: List of tuples (word, pos, is_regular, translation, difficulty)
              Ordered alphabetically by word
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            # Build query
            query = f"SELECT word, pos, is_regular, translation, difficulty FROM {TABLE_NAME}"
            params = []
            conditions = []

            # Add difficulty filter if provided
            if filters and 'difficulty' in filters:
                conditions.append("difficulty = ?")
                params.append(filters['difficulty'])

            # Add search filter if provided
            if search_term:
                conditions.append("(word LIKE ? OR translation LIKE ?)")
                search_pattern = f"%{search_term}%"
                params.extend([search_pattern, search_pattern])

            # Add WHERE clause if any conditions
            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            # Add ordering
            query += " ORDER BY word ASC"

            cursor.execute(query, params)
            return cursor.fetchall()

    except sqlite3.Error as e:
        print(f"Database error in get_all_words: {e}")
        return []


def get_all_sessions():
    """
    Get all processing sessions from temp_vocab table.

    Returns:
        list: List of tuples (session_id, word_count, created_at)
              Ordered by created_at DESC (newest first)
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    session_id,
                    COUNT(*) as word_count,
                    MIN(created_at) as created_at
                FROM temp_vocab
                GROUP BY session_id
                ORDER BY created_at DESC
            """)
            return cursor.fetchall()

    except sqlite3.Error as e:
        print(f"Database error in get_all_sessions: {e}")
        return []


def get_session_stats(session_id):
    """
    Get statistics for a specific session.

    Args:
        session_id: The session ID to get stats for

    Returns:
        dict: {'total': int, 'pending': int}
              Returns {'total': 0, 'pending': 0} if session not found
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            # Count total words in session
            cursor.execute("""
                SELECT COUNT(*) FROM temp_vocab WHERE session_id = ?
            """, (session_id,))
            total = cursor.fetchone()[0]

            # Pending count is same as total (words in temp_vocab are pending)
            pending = total

            return {
                'total': total,
                'pending': pending
            }

    except sqlite3.Error as e:
        print(f"Database error in get_session_stats: {e}")
        return {'total': 0, 'pending': 0}


def get_word_count():
    """
    Get total number of words in main vocabulary.

    Returns:
        int: Total word count
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
            return cursor.fetchone()[0]

    except sqlite3.Error as e:
        print(f"Database error in get_word_count: {e}")
        return 0


# Initialize database when this module is imported
init_database()
