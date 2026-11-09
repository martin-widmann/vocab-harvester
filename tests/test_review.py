"""Vocab review: due cards for Taught words on an FSRS schedule."""

from datetime import datetime, timedelta, timezone

import pytest

from core import EpisodeLine, VocabStore, WordState, due_cards, grade_card
from fakes import FakeDateClock

EPISODE = "Test/S01E01"
START = datetime(2026, 11, 9, 8, 0, tzinfo=timezone.utc)


@pytest.fixture
def store(tmp_path):
    store = VocabStore(tmp_path / "vocab.sqlite")
    yield store
    store.close()


@pytest.fixture
def clock():
    return FakeDateClock(START)


def taught(store, base_form, word_type="VERB", *, line=None, seen_form=None,
           meaning="a meaning", gender=None, sentences=()):
    """A word as a finished Lesson leaves it: Taught, with its Lesson facts."""
    store.add(base_form, word_type, WordState.UNKNOWN)
    if line is not None:
        store.keep_lesson_word(
            base_form, EpisodeLine(EPISODE, 3, line, seen_form), meaning, gender
        )
    for number, sentence in enumerate(sentences, start=1):
        store.add_example_sentence(base_form, number, sentence)
    store.teach(base_form, EPISODE)


def test_a_taught_word_is_due_at_once_with_its_episode_line_and_the_word_in_bold(store, clock):
    taught(store, "aufgeben", line="Er gab nicht auf.", seen_form="gab auf",
           meaning="to give up", sentences=["Sie gibt nie auf."])

    (card,) = due_cards(store, clock)

    assert card.base_form == "aufgeben"
    assert card.seen_form == "gab auf"
    assert card.context == "Er **gab** nicht **auf**."
    assert card.meaning == "to give up"
    assert card.needs_article is False


def test_only_taught_words_get_vocab_reviews(store, clock):
    store.add("gehen", "VERB", WordState.KNOWN)
    store.add("suchen", "VERB", WordState.UNKNOWN)
    store.add("Martha", "PROPN", WordState.EXCLUDED)
    taught(store, "aufgeben", line="Er gab nicht auf.", seen_form="gab auf")

    assert [card.base_form for card in due_cards(store, clock)] == ["aufgeben"]


def test_a_taught_word_that_changed_state_gets_no_more_reviews(store, clock):
    taught(store, "aufgeben", line="Er gab nicht auf.", seen_form="gab auf")
    store.set_state("aufgeben", WordState.UNKNOWN)

    assert due_cards(store, clock) == []


@pytest.mark.parametrize(
    "rating, wait",
    [
        # The py-fsrs defaults: learning steps of 1 and 10 minutes; Easy
        # leaves the learning steps with the first stability of Easy, 8 days.
        ("Again", timedelta(minutes=1)),
        ("Good", timedelta(minutes=10)),
        ("Easy", timedelta(days=8)),
    ],
)
def test_the_self_grade_sets_the_next_review_date_with_fsrs(store, clock, rating, wait):
    taught(store, "aufgeben", line="Er gab nicht auf.", seen_form="gab auf")

    graded = grade_card(store, "aufgeben", rating, clock)

    assert graded.rating == rating
    assert graded.due == START + wait
    clock.time = START + wait - timedelta(seconds=1)
    assert due_cards(store, clock) == []
    clock.time = START + wait
    assert [card.base_form for card in due_cards(store, clock)] == ["aufgeben"]


def test_a_harder_grade_brings_the_card_back_sooner(store, clock):
    for word in ("eins", "zwei", "drei", "vier"):
        taught(store, word, sentences=[f"Satz mit {word}."])

    dues = [
        grade_card(store, word, rating, clock).due
        for word, rating in zip(("eins", "zwei", "drei", "vier"), ("Again", "Hard", "Good", "Easy"))
    ]

    assert dues == sorted(dues)
    assert len(set(dues)) == 4


def test_the_next_reviews_build_on_the_saved_card(store, clock):
    taught(store, "aufgeben", sentences=["Sie gibt nie auf."])
    first = grade_card(store, "aufgeben", "Good", clock).due
    clock.time = first
    second = grade_card(store, "aufgeben", "Good", clock).due

    assert second - first >= timedelta(days=1)


@pytest.mark.parametrize("rating", ["", "Okay", "5"])
def test_a_grade_that_is_not_again_hard_good_or_easy_is_rejected(store, clock, rating):
    taught(store, "aufgeben", sentences=["Sie gibt nie auf."])

    with pytest.raises(ValueError, match="Again, Hard, Good or Easy"):
        grade_card(store, "aufgeben", rating, clock)


def test_a_card_that_is_not_due_cannot_be_graded(store, clock):
    taught(store, "aufgeben", sentences=["Sie gibt nie auf."])
    store.add("gehen", "VERB", WordState.KNOWN)
    grade_card(store, "aufgeben", "Easy", clock)

    for word in ("aufgeben", "gehen", "fehlt"):
        with pytest.raises(ValueError, match="no vocab card due today"):
            grade_card(store, word, "Good", clock)


def review_until_due_again(store, clock, base_form):
    """Grade the card Again and wait until it is due again; give the next card."""
    clock.time = grade_card(store, base_form, "Again", clock).due
    (card,) = due_cards(store, clock)
    return card


def test_later_reviews_show_a_different_example_sentence_each_time(store, clock):
    taught(store, "aufgeben", line="Er gab nicht auf.", seen_form="gab auf",
           sentences=["Satz eins.", "Satz zwei.", "Satz drei."])

    (first,) = due_cards(store, clock)
    later = [review_until_due_again(store, clock, "aufgeben") for _ in range(4)]

    assert first.first_review is True
    assert [card.first_review for card in later] == [False] * 4
    assert [card.context for card in later] == [
        "Satz eins.", "Satz zwei.", "Satz drei.", "Satz eins.",
    ]
    # Every card shows the Base form and the Seen form.
    assert {(card.base_form, card.seen_form) for card in [first, *later]} == {
        ("aufgeben", "gab auf")
    }


def test_a_word_with_no_episode_line_shows_its_example_sentences(store, clock):
    taught(store, "aufgeben", sentences=["Satz eins.", "Satz zwei."])

    (first,) = due_cards(store, clock)
    second = review_until_due_again(store, clock, "aufgeben")

    assert (first.context, first.first_review, first.seen_form) == ("Satz eins.", False, None)
    assert second.context == "Satz zwei."


def test_a_word_with_no_example_sentences_shows_its_episode_line_again(store, clock):
    taught(store, "aufgeben", line="Er gab nicht auf.", seen_form="gab auf")

    later = review_until_due_again(store, clock, "aufgeben")

    assert later.context == "Er **gab** nicht **auf**."


@pytest.mark.parametrize(
    "line, seen_form, context",
    [
        ("Gibst du auf?", "Gibst auf", "**Gibst** du **auf**?"),
        ("Ich suche, du suchst.", "suchst", "Ich suche, du **suchst**."),
        ("Sie hilft dem alten Mann.\n- Gut.", "hilft", "Sie **hilft** dem alten Mann.\n- Gut."),
        ("Nichts davon.", "gab", "Nichts davon."),
    ],
    ids=["two parts", "whole word", "two rows", "not found"],
)
def test_the_seen_form_is_bold_in_the_episode_line(store, clock, line, seen_form, context):
    taught(store, "wort", line=line, seen_form=seen_form)

    (card,) = due_cards(store, clock)

    assert card.context == context


def test_a_noun_needs_its_typed_article_and_a_script_checks_it(store, clock):
    taught(store, "Höhle", "NOUN", line="Die Höhle ist dunkel.", seen_form="Höhle",
           gender="feminine")
    taught(store, "Hund", "NOUN", line="Der Hund bellt.", seen_form="Hund",
           gender="masculine")

    assert [card.needs_article for card in due_cards(store, clock)] == [True, True]
    right = grade_card(store, "Höhle", "Good", clock, article=" Die ")
    wrong = grade_card(store, "Hund", "Good", clock, article="das")

    assert right.article.right is True
    assert right.article.correction == "die Höhle"
    assert wrong.article.right is False
    assert wrong.article.correction == "der Hund"
    assert wrong.article.reason == "Hund is masculine: der Hund."
    assert wrong.rating == "Good"  # The grade stays the learner's own.


@pytest.mark.parametrize("article", [None, "", "den", "die Höhle"])
def test_a_noun_review_without_der_die_or_das_is_rejected_and_not_saved(store, clock, article):
    taught(store, "Höhle", "NOUN", line="Die Höhle ist dunkel.", seen_form="Höhle",
           gender="feminine")

    with pytest.raises(ValueError, match="Type der, die or das"):
        grade_card(store, "Höhle", "Good", clock, article=article)
    assert due_cards(store, clock)[0].first_review is True


def test_other_words_take_no_article(store, clock):
    taught(store, "aufgeben", line="Er gab nicht auf.", seen_form="gab auf")
    taught(store, "Angst", "NOUN", line="Ich habe Angst.", seen_form="Angst", gender=None)

    assert [card.needs_article for card in due_cards(store, clock)] == [False, False]
    assert grade_card(store, "Angst", "Good", clock).article is None
    with pytest.raises(ValueError, match="takes no article"):
        grade_card(store, "aufgeben", "Good", clock, article="der")


def teach_many(store, count):
    words = [f"wort{number:02}" for number in range(count)]
    for word in words:
        taught(store, word, sentences=[f"Satz mit {word}."])
    return words


def test_at_most_50_vocab_cards_a_day_the_rest_move_to_the_next_day(store, clock):
    words = teach_many(store, 60)

    assert [card.base_form for card in due_cards(store, clock)] == words[:50]
    for word in words[:50]:
        grade_card(store, word, "Easy", clock)
    assert due_cards(store, clock) == []
    with pytest.raises(ValueError, match="no vocab card due today"):
        grade_card(store, words[50], "Good", clock)

    clock.time = START + timedelta(days=1)
    assert [card.base_form for card in due_cards(store, clock)] == words[50:]


def test_a_card_reviewed_today_comes_back_after_again_beyond_the_limit(store, clock):
    words = teach_many(store, 51)
    for word in words[:49]:
        grade_card(store, word, "Easy", clock)
    grade_card(store, words[49], "Again", clock)

    clock.advance(minutes=1)

    assert [card.base_form for card in due_cards(store, clock)] == [words[49]]


def test_cards_due_longest_come_first_then_new_cards(store, clock):
    taught(store, "alt", sentences=["Satz mit alt."])
    taught(store, "mitte", sentences=["Satz mit mitte."])
    grade_card(store, "mitte", "Good", clock)  # Due in 10 minutes.
    clock.advance(minutes=5)
    grade_card(store, "alt", "Again", clock)  # Due in 1 minute.
    taught(store, "neu", sentences=["Satz mit neu."])

    clock.advance(minutes=10)

    assert [card.base_form for card in due_cards(store, clock)] == ["alt", "mitte", "neu"]


def test_the_review_day_is_the_date_of_the_learners_time_zone(store, clock):
    words = teach_many(store, 51)
    berlin = timezone(timedelta(hours=1))
    clock.time = datetime(2026, 11, 9, 23, 30, tzinfo=berlin)
    for word in words[:50]:
        grade_card(store, word, "Easy", clock)

    clock.time = datetime(2026, 11, 10, 0, 10, tzinfo=berlin)  # Still 9 Nov in UTC.

    assert [card.base_form for card in due_cards(store, clock)] == [words[50]]


def test_a_clock_with_no_time_zone_is_rejected(store, clock):
    taught(store, "aufgeben", sentences=["Sie gibt nie auf."])
    clock.time = datetime(2026, 11, 9, 8, 0)

    with pytest.raises(ValueError, match="time zone"):
        due_cards(store, clock)
