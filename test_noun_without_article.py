"""Test if spaCy can extract gender from nouns appearing WITHOUT articles."""

import spacy

nlp = spacy.load("de_core_news_sm")

# Test with nouns in various contexts (no articles)
test_cases = [
    "Mann isst Brot",           # No articles at all
    "Katze jagt Maus",          # Feminine and feminine
    "Ich liebe Hunde",          # Plural
    "Tische sind teuer",        # Plural
    "Buch gefunden",            # Neuter without article
]

print("Testing gender detection for nouns WITHOUT articles")
print("=" * 80)

for text in test_cases:
    print(f"\nText: '{text}'")
    doc = nlp(text)

    for token in doc:
        if token.pos_ == "NOUN":
            gender = token.morph.get("Gender")
            number = token.morph.get("Number")
            print(f"  NOUN: {token.text} (lemma: {token.lemma_})")
            print(f"    Gender: {gender if gender else 'NOT FOUND'}")
            print(f"    Number: {number if number else 'NOT FOUND'}")

print("\n" + "=" * 80)
print("CONCLUSION: Can we rely on spaCy for article/gender info?")
print("=" * 80)
