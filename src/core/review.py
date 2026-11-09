"""Vocab review: due cards for Taught words on an FSRS schedule (py-fsrs).

Only Taught words get vocab reviews. A card always shows the word in
context: the first review shows the episode Line with the word in bold,
later reviews show the example sentences in turn. The learner grades
themselves (Again, Hard, Good, Easy); FSRS sets the next review date. For a
noun the learner also types der, die or das, and a script checks it. At most
50 cards a day: the rest stay due and come the next day.

A word's first review is due the day after its Lesson: the Lesson comes
before watching, and the episode Line would spoil the Episode.
"""

import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from fsrs import Card, Rating, Scheduler

from core.lesson import ARTICLES
from core.results import Result
from core.vocab_store import ReviewData, VocabStore

DAILY_CARD_LIMIT = 50

# No fuzzing: the same reviews give the same dates, so a test can check them.
_SCHEDULER = Scheduler(enable_fuzzing=False)
_RATINGS = {rating.name: rating for rating in Rating}
# The web server grades in more than one thread: one grade at a time, so a
# double click cannot review a card twice.
_GRADE_LOCK = threading.Lock()


class Clock(Protocol):
    def now(self) -> datetime:
        """The time now, with the learner's time zone: its date is the review day."""


class SystemDateClock:
    """The computer's clock, in its own time zone."""

    def now(self) -> datetime:
        return datetime.now().astimezone()


@dataclass(frozen=True)
class ReviewCard:
    """A due vocab card as the Review tab shows it.

    `context` is what the card shows: the episode Line with the word in
    **bold** (`first_review` is True), or an example sentence.
    `needs_article` is True for a noun: the learner types der, die or das.
    """

    base_form: str
    word_type: str
    seen_form: str | None
    context: str
    first_review: bool
    meaning: str | None
    needs_article: bool


@dataclass(frozen=True)
class Graded:
    """A saved review: the next review date, and the article result of a noun."""

    base_form: str
    rating: str
    due: datetime
    article: Result | None


def due_cards(store: VocabStore, clock: Clock) -> list[ReviewCard]:
    """Today's due vocab cards: the cards due longest first, then new ones.

    A card the learner already reviewed today (for example after Again)
    comes back when it is due. Other cards fill only the rest of the daily
    limit of 50 cards; the others stay due and come the next day.
    """
    return [_card(store, data) for data in _due(store, _now(clock))]


def grade_card(
    store: VocabStore,
    base_form: str,
    rating: str,
    clock: Clock,
    *,
    article: str | None = None,
) -> Graded:
    """Save the learner's grade of a due card; FSRS sets its next review date.

    `rating` is Again, Hard, Good or Easy. A noun needs its typed article,
    which a script checks; the grade stays the learner's own. A card that is
    not due today is rejected.
    """
    found = _RATINGS.get(rating.strip().capitalize())
    if found is None:
        raise ValueError("Grade the card Again, Hard, Good or Easy")
    with _GRADE_LOCK:
        now = _now(clock)
        data = next(
            (data for data in _due(store, now) if data.base_form == base_form), None
        )
        if data is None:
            raise ValueError(f"{base_form!r} has no vocab card due today")
        checked = _checked_article(data, article)
        utc = now.astimezone(timezone.utc)
        card = Card.from_json(data.card) if data.card else Card(card_id=1, due=utc)
        card, _ = _SCHEDULER.review_card(card, found, review_datetime=utc)
        store.save_review(
            base_form,
            card.to_json(),
            utc.isoformat(),
            now.date(),
            found.name,
            None if checked is None else checked.right,
        )
    return Graded(base_form, found.name, card.due, checked)


def _now(clock: Clock) -> datetime:
    now = clock.now()
    if now.tzinfo is None:
        raise ValueError("The review clock must give the time with its time zone")
    return now


def _due(store: VocabStore, now: datetime) -> list[ReviewData]:
    utc = now.astimezone(timezone.utc)
    today = now.date()
    done_today = store.reviewed_on(today)
    due = []
    new = []
    for data in store.review_data():
        if data.card is None:
            if data.teaching is None or data.teaching.day < today:
                new.append(data)
            continue
        card_due = Card.from_json(data.card).due
        if card_due <= utc:
            due.append((card_due, data))
    ordered = [data for _, data in sorted(due, key=lambda pair: pair[0])] + new
    room = DAILY_CARD_LIMIT - len(done_today)
    picked = []
    for data in ordered:
        if data.base_form in done_today:
            picked.append(data)
        elif room > 0:
            picked.append(data)
            room -= 1
    return picked


def _card(store: VocabStore, data: ReviewData) -> ReviewCard:
    teaching = data.teaching
    seen_form = None if teaching is None else teaching.seen_form
    line = data.line
    sentences = [sentence for _, sentence in sorted(store.example_sentences(data.base_form).items())]
    # The first review shows the episode Line; each later review the next
    # example sentence. A word with no episode Line starts with the sentences.
    first = line is not None and data.reviews == 0
    if first or (line is not None and not sentences):
        context = _in_bold(line.text, seen_form or "")
    elif sentences:
        later = data.reviews - 1 if line is not None else data.reviews
        context = sentences[later % len(sentences)]
    else:
        context = ""
    return ReviewCard(
        base_form=data.base_form,
        word_type=data.word_type,
        seen_form=seen_form,
        context=context,
        first_review=first,
        meaning=None if teaching is None else teaching.meaning,
        needs_article=_gender(data) in ARTICLES,
    )


def _in_bold(text: str, seen_form: str) -> str:
    """The text with each part of the Seen form in **bold**, in their order."""
    start = 0
    for part in seen_form.split():
        pattern = re.compile(rf"(?<!\w){re.escape(part)}(?!\w)")
        match = pattern.search(text, start) or re.compile(
            pattern.pattern, re.IGNORECASE
        ).search(text, start)
        if match is None:
            continue
        text = f"{text[:match.start()]}**{match.group()}**{text[match.end():]}"
        start = match.end() + 4
    return text


def _gender(data: ReviewData) -> str | None:
    return None if data.teaching is None else data.teaching.gender


def _checked_article(data: ReviewData, article: str | None) -> Result | None:
    gender = _gender(data)
    if gender not in ARTICLES:
        if article:
            raise ValueError(f"{data.base_form!r} is not a noun; it takes no article")
        return None
    given = " ".join((article or "").split()).casefold()
    if given not in ARTICLES.values():
        raise ValueError("Type der, die or das")
    expected = ARTICLES[gender]
    return Result(
        given == expected,
        f"{expected} {data.base_form}",
        f"{data.base_form} is {gender}: {expected} {data.base_form}.",
    )
