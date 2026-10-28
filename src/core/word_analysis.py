"""Word analysis: reduce the text of a Line to Base forms with spaCy."""

import re
from dataclasses import dataclass
from functools import cache

import spacy
from spacy.tokens import Token

_MARKUP = re.compile(r"<[^>]*>|\{[^}]*\}")

# Not vocabulary: punctuation, numbers, symbols, spaces, unknown,
# interjections.
_SKIPPED_TYPES = {"PUNCT", "NUM", "SYM", "SPACE", "X", "INTJ"}

# spaCy often tags filler sounds as nouns or names: "Äh", "ähm", "Hmm".
_FILLER = re.compile(
    r"(ä+h+m*|ö+h+m*|e+h+m+|h+m+|m+h+m+|ah+|oh+|uh+m*)", re.IGNORECASE
)


@dataclass(frozen=True)
class Word:
    """One word of a Line: its Base form, word type and Seen form."""

    base_form: str
    word_type: str
    seen_form: str


@cache
def _nlp() -> spacy.Language:
    return spacy.load("de_core_news_sm")


def analyse(text: str) -> list[Word]:
    """Reduce the text of a Line to its Words, in text order.

    Separable verbs are joined: "Er gab nicht auf" gives "aufgeben".
    Names, places and filler sounds are left out.
    """
    doc = _nlp()(_MARKUP.sub("", text).replace("\n", " "))
    return [_word(token) for token in doc if _is_vocab(token)]


def _is_vocab(token: Token) -> bool:
    return not (
        token.pos_ in _SKIPPED_TYPES
        or _is_verb_particle(token)
        or _is_name_or_place(token)
        or _FILLER.fullmatch(token.text)
    )


def _is_verb_particle(token: Token) -> bool:
    return token.dep_ == "svp" and token.head.pos_ in {"VERB", "AUX"}


def _is_name_or_place(token: Token) -> bool:
    # "NE" is the tag for a proper noun. Entity types are not used: spaCy
    # puts common nouns ("Mama", "Gott") into them too. A name that slips
    # through is marked Excluded in the Word Knowledge Check.
    return token.tag_ == "NE"


def _word(token: Token) -> Word:
    particles = [child for child in token.children if _is_verb_particle(child)]
    base_form = "".join(p.text.lower() for p in particles) + token.lemma_
    seen_form = " ".join([token.text, *(p.text for p in particles)])
    return Word(_cased(base_form, token.pos_), token.pos_, seen_form)


def _cased(base_form: str, word_type: str) -> str:
    # Nouns start with a capital letter; spaCy keeps the capital of other
    # words at the start of a sentence, so they are made lower case.
    if word_type in {"NOUN", "PROPN"}:
        return base_form[:1].upper() + base_form[1:]
    return base_form.lower()
