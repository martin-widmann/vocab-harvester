import spacy
import re
from database import add_word, word_exists, add_tag_to_word

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
        else:
            print(f"Skipping '{lemma}' (already in database)")
    
    return unknown_words

def process_text_input(raw_text, interactive=True):
    """Main pipeline: Text Input � Tokenization � Lemmatization � Filter Known Words � Database Storage"""
    
    # Step 1: Text Input Handler
    cleaned_text = clean_text_input(raw_text)
    if not cleaned_text:
        print("No valid text to process.")
        return
    
    # Step 2: Tokenization Engine  
    tokens = tokenize_text(cleaned_text)
    if not tokens:
        print("No valid words found in text.")
        return
    
    # Step 3: Lemmatization Pipeline
    lemmatized_words = lemmatize_words(tokens)
    if not lemmatized_words:
        print("No words to lemmatize.")
        return
    
    # Step 4: Known Word Filter
    unknown_words = filter_known_words(lemmatized_words)
    if not unknown_words:
        print("No new words found in text.")
        return
    
    print(f"Found {len(unknown_words)} new words to process.")
    
    # Step 5: New Word Tagger & Database Writer
    for word_data in unknown_words:
        lemma = word_data['lemma']
        pos = word_data['pos']
        original = word_data['original']
        
        if interactive:
            # Prompt user for action
            action = None
            while action not in {"A", "S", "Q"}:
                print(f"\nWord: {original} � Lemma: {lemma} | POS: {pos}")
                action = input("Add (A), Skip (S), Quit (Q): ").strip().upper()
            
            if action == "Q":
                print("Processing stopped by user.")
                break
            elif action == "S":
                continue
            
            # If user chose to add the word, ask for tags
            tags_input = input("Enter tags (comma-separated, or press Enter for none): ").strip()
            user_tags = [tag.strip() for tag in tags_input.split(",") if tag.strip()] if tags_input else []
        
        # Automatically determine if verb is irregular
        if pos in {"VERB", "AUX"}:
            is_regular = lemma not in IRREGULAR_VERBS
        else:
            is_regular = None
        
        # Add to database
        add_word(lemma, pos, is_regular)
        
        # Add user-specified tags
        if interactive and 'user_tags' in locals() and user_tags:
            for tag in user_tags:
                add_tag_to_word(lemma, tag)
    
    print("Text processing complete.")