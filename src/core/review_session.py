"""Finish a review session on the Review tab.

Each grade and each grammar answer changes the learner state at once, when
it is given. Finish then sums up the review day and makes the learner
summary again, so the tutor sees the new state at the next session.
"""

from dataclasses import dataclass

from core.curriculum import Curriculum
from core.grammar_review import due_grammar
from core.grammar_topics import ExerciseStock
from core.learner_summary import LearnerSummary
from core.lesson import LessonFiles
from core.review import Clock, due_cards
from core.vocab_store import VocabStore


@dataclass(frozen=True)
class ReviewDay:
    """The reviews of today's review day, and what is still due today."""

    vocab_reviews: int
    vocab_again: int
    wrong_articles: int
    grammar_reviews: int
    grammar_right: int
    vocab_due: int
    grammar_due: int


def finish_review(
    *,
    store: VocabStore,
    curriculum: Curriculum,
    stock: ExerciseStock,
    lessons: LessonFiles,
    summary: LearnerSummary,
    clock: Clock,
) -> ReviewDay:
    """Finish a review session: sum up the review day and make the summary again.

    The learner can finish more than once a day; each Finish sums up the
    whole day so far.
    """
    now = clock.now()
    if now.tzinfo is None:
        raise ValueError("The review clock must give the time with its time zone")
    today = now.date()
    vocab = store.review_log(today)
    grammar = stock.review_results(today)
    day = ReviewDay(
        vocab_reviews=len(vocab),
        vocab_again=sum(1 for review in vocab if review.rating == "Again"),
        wrong_articles=sum(1 for review in vocab if review.article_right is False),
        grammar_reviews=len(grammar),
        grammar_right=sum(grammar),
        vocab_due=len(due_cards(store, clock)),
        grammar_due=len(due_grammar(curriculum, stock, clock)),
    )
    summary.regenerate(store=store, curriculum=curriculum, lessons=lessons, today=today)
    return day
