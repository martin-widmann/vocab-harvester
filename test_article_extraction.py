"""Test script to check if spaCy can extract article/gender information from German nouns."""

import spacy

# Load German model
nlp = spacy.load("de_core_news_sm")

# Test sentences with German nouns (with articles)
test_texts = [
    "der Mann",      # masculine
    "die Frau",      # feminine
    "das Kind",      # neuter
    "der Tisch geht",    # masculine
    "die Katze läuft",   # feminine
    "das Buch liegt",    # neuter
    "Der große Hund bellt",  # masculine with adjective
]

print("=" * 80)
print("SPACY GERMAN NOUN ANALYSIS")
print("=" * 80)

for text in test_texts:
    print(f"\nText: '{text}'")
    print("-" * 80)

    doc = nlp(text)

    for token in doc:
        print(f"\nToken: {token.text}")
        print(f"  Lemma: {token.lemma_}")
        print(f"  POS: {token.pos_}")
        print(f"  Tag: {token.tag_}")
        print(f"  Dep: {token.dep_}")
        print(f"  Morph: {token.morph}")

        # Check for gender in morphological features
        if token.morph.get("Gender"):
            print(f"  ** GENDER FOUND: {token.morph.get('Gender')}")

        # Check if it's a determiner (article)
        if token.pos_ == "DET":
            print(f"  ** ARTICLE DETECTED")

        # Check noun-article relationship
        if token.pos_ == "NOUN":
            print(f"  ** NOUN DETECTED")
            # Check if there's a determiner child or head
            for child in token.children:
                if child.pos_ == "DET":
                    print(f"  -> Associated article: {child.text}")
            if token.head.pos_ == "DET":
                print(f"  -> Head article: {token.head.text}")

print("\n" + "=" * 80)
print("SUMMARY: Checking what gender/article info is available")
print("=" * 80)
