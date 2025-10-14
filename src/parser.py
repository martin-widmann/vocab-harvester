import spacy
import re
import uuid
from datetime import datetime
from database import word_exists, add_temp_word, temp_word_exists
from translation import get_best_translation

# Load German NLP model
nlp = spacy.load("de_core_news_sm")

# Load irregular verbs into a set for fast lookup
with open("C:/Users/marti/Projects-2025/vocab-harvester/data/irregular_Verbs.txt", "r", encoding="utf-8") as f:
    IRREGULAR_VERBS = set(line.strip() for line in f if line.strip())


def clean_text_input(raw_text):
    """Accept and validate text input, return cleaned text ready for processing."""
    if not raw_text or not raw_text.strip():
        return ""

    # Basic text cleaning
    cleaned = raw_text.strip()
    # Remove excessive whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned)

    return cleaned


def tokenize_text(text):
    """Break text into individual word tokens using spaCy."""
    if not text:
        return []

    doc = nlp(text)
    # Extract tokens that are actual words (not punctuation, whitespace, etc.)
    tokens = [token.text.lower() for token in doc if token.is_alpha]

    return tokens


def lemmatize_words(tokens):
    """Convert word tokens to base forms using spaCy."""
    if not tokens:
        return []

    # Process all tokens at once for efficiency
    text_to_process = " ".join(tokens)
    doc = nlp(text_to_process)

    lemmatized = []
    for token in doc:
        if token.is_alpha:  # Only process alphabetic tokens
            lemmatized.append({
                'original': token.text.lower(),
                'lemma': token.lemma_.lower(),
                'pos': token.pos_
            })

    return lemmatized


def filter_known_words(lemmatized_words):
    """Check words against existing vocabulary database, return only unknown words."""
    unknown_words = []

    for word_data in lemmatized_words:
        lemma = word_data['lemma']
        if not word_exists(lemma):
            unknown_words.append(word_data)

    return unknown_words


def process_text_input(raw_text, session_id=None):
    """Main pipeline: Text Input → Tokenization → Lemmatization → Filter Known Words → Temp Database Storage"""

    # Generate session ID if not provided
    if session_id is None:
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"

    # Step 1: Text Input Handler
    cleaned_text = clean_text_input(raw_text)
    if not cleaned_text:
        return None

    # Step 2: Tokenization Engine
    tokens = tokenize_text(cleaned_text)
    if not tokens:
        return None

    # Step 3: Lemmatization Pipeline
    lemmatized_words = lemmatize_words(tokens)
    if not lemmatized_words:
        return None

    # Step 4: Known Word Filter
    unknown_words = filter_known_words(lemmatized_words)
    if not unknown_words:
        return {
            'session_id': session_id,
            'words_processed': 0,
            'words_added': 0,
            'words_translated': 0
        }

    # Step 5: Process words with automatic translation and temp database storage
    added_count = 0
    translated_count = 0

    for word_data in unknown_words:
        lemma = word_data['lemma']
        pos = word_data['pos']
        original = word_data['original']

        # Check if word already exists in temp database for this session
        if temp_word_exists(original, session_id):
            continue

        # Automatically determine if verb is irregular
        if pos in {"VERB", "AUX"}:
            is_regular = lemma not in IRREGULAR_VERBS
        else:
            is_regular = None

        # Attempt to get translation automatically
        translation = get_best_translation(lemma, pos)
        if translation:
            translated_count += 1

        # Add to temporary database with translation (if available)
        success = add_temp_word(original, lemma, pos, translation, is_regular, session_id)
        if success:
            added_count += 1

    # Return processing results
    return {
        'session_id': session_id,
        'words_processed': len(unknown_words),
        'words_added': added_count,
        'words_translated': translated_count
    }
