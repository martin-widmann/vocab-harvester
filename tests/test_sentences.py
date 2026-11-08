import pytest

from fakes import FakeClock, FakeLanguageTool

from core import (
    LanguageToolBusy,
    SentenceChecker,
    SentenceStatus,
    SentenceToStore,
    VocabStore,
    WordState,
    add_sentences,
    failed_sentences,
)


@pytest.fixture
def store(tmp_path):
    store = VocabStore(tmp_path / "vocab.sqlite")
    store.add("aufgeben", "VERB", WordState.UNKNOWN)
    store.add("Höhle", "NOUN", WordState.UNKNOWN)
    return store


@pytest.fixture
def language_tool():
    return FakeLanguageTool()


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def checker(language_tool, clock):
    return SentenceChecker(language_tool, clock)


def test_sentences_that_pass_languagetool_are_stored_as_example_sentences(store, checker):
    results = add_sentences(
        store,
        checker,
        [
            SentenceToStore("aufgeben", 1, "Er gibt nie auf."),
            SentenceToStore("aufgeben", 2, "Sie hat das Rauchen aufgegeben."),
        ],
    )

    assert [result.status for result in results] == ["stored", "stored"]
    assert store.example_sentences("aufgeben") == {
        1: "Er gibt nie auf.",
        2: "Sie hat das Rauchen aufgegeben.",
    }


def test_a_failed_sentence_is_not_stored_and_can_be_retried_3_times(store, checker):
    (result,) = add_sentences(
        store, checker, [SentenceToStore("aufgeben", 1, "Er gibt falsch auf.")]
    )

    assert result.status == "retry"
    assert result.problems == ["Fehler: falsch"]
    assert result.retries_left == 3
    assert store.example_sentences("aufgeben") == {}


def test_a_retry_that_passes_is_stored(store, checker):
    add_sentences(store, checker, [SentenceToStore("aufgeben", 1, "Er gibt falsch auf.")])

    (result,) = add_sentences(
        store, checker, [SentenceToStore("aufgeben", 1, "Er gibt nie auf.")]
    )

    assert (result.status, result.retries_left) == ("stored", None)
    assert store.example_sentences("aufgeben") == {1: "Er gibt nie auf."}


def test_after_3_failed_retries_the_sentence_goes_on_the_list_for_the_learner(
    store, checker
):
    tries = [f"Versuch {n} ist falsch." for n in range(1, 5)]

    results = [
        add_sentences(store, checker, [SentenceToStore("aufgeben", 2, text)])[0]
        for text in tries
    ]

    assert [(r.status, r.retries_left) for r in results] == [
        ("retry", 3),
        ("retry", 2),
        ("retry", 1),
        ("listed", 0),
    ]
    assert store.example_sentences("aufgeben") == {}
    (failed,) = failed_sentences(store)
    assert failed.status == SentenceStatus.LISTED
    assert (failed.base_form, failed.number, failed.sentence, failed.problems) == (
        "aufgeben",
        2,
        "Versuch 4 ist falsch.",
        ["Fehler: falsch"],
    )


def test_the_tries_of_one_sentence_do_not_count_for_another(store, checker):
    for number in (1, 2, 3):
        add_sentences(store, checker, [SentenceToStore("aufgeben", number, "falsch")])
    (other_word,) = add_sentences(store, checker, [SentenceToStore("Höhle", 1, "falsch")])

    assert other_word.retries_left == 3
    assert [failed.status for failed in failed_sentences(store)] == ["retry"] * 4


def test_a_failed_sentence_not_yet_retried_is_on_the_list_for_the_learner(store, checker):
    add_sentences(store, checker, [SentenceToStore("aufgeben", 1, "Das ist falsch.")])

    (failed,) = failed_sentences(store)

    assert (failed.sentence, failed.status, failed.retries_left) == (
        "Das ist falsch.",
        SentenceStatus.RETRY,
        3,
    )


def test_a_retry_that_passes_takes_the_sentence_off_the_list(store, checker):
    add_sentences(store, checker, [SentenceToStore("aufgeben", 1, "Das ist falsch.")])
    add_sentences(store, checker, [SentenceToStore("aufgeben", 1, "Er gibt nie auf.")])

    assert failed_sentences(store) == []


def test_a_sentence_on_the_list_for_the_learner_takes_no_more_tries(store, checker):
    for _ in range(4):
        add_sentences(store, checker, [SentenceToStore("aufgeben", 1, "falsch")])

    with pytest.raises(ValueError, match="list for the learner"):
        add_sentences(store, checker, [SentenceToStore("aufgeben", 1, "Er gibt nie auf.")])


@pytest.mark.parametrize(
    "bad, reason",
    [
        (SentenceToStore("Polizei", 1, "Die Polizei kommt."), "not an Unknown or Taught word"),
        (SentenceToStore("Mikkel", 1, "Mikkel ist weg."), "not an Unknown or Taught word"),
        (SentenceToStore("aufgeben", 0, "Er gibt auf."), "1, 2 or 3"),
        (SentenceToStore("aufgeben", 4, "Er gibt auf."), "1, 2 or 3"),
        (SentenceToStore("aufgeben", 1, "   "), "empty"),
        (SentenceToStore("aufgeben", 1, "Er gibt auf. " * 40), "too long"),
        (SentenceToStore("aufgeben", 1, "Er gibt\nauf."), "one line"),
    ],
)
def test_a_bad_sentence_rejects_the_whole_call_before_languagetool_runs(
    store, checker, language_tool, bad, reason
):
    store.add("Polizei", "NOUN", WordState.KNOWN)
    good = SentenceToStore("Höhle", 1, "Die Höhle ist dunkel.")

    with pytest.raises(ValueError, match=reason):
        add_sentences(store, checker, [good, bad])

    assert language_tool.texts == []
    assert store.example_sentences("Höhle") == {}


def test_a_stored_sentence_cannot_be_replaced(store, checker, language_tool):
    add_sentences(store, checker, [SentenceToStore("aufgeben", 1, "Er gibt nie auf.")])

    with pytest.raises(ValueError, match="already stored"):
        add_sentences(store, checker, [SentenceToStore("aufgeben", 1, "Gib nicht auf!")])


def test_one_call_cannot_give_the_same_sentence_number_twice(store, checker):
    with pytest.raises(ValueError, match="twice"):
        add_sentences(
            store,
            checker,
            [
                SentenceToStore("aufgeben", 1, "Er gibt nie auf."),
                SentenceToStore("aufgeben", 1, "Gib nicht auf!"),
            ],
        )


def test_sentences_for_a_taught_word_are_stored(tmp_path, checker):
    store = VocabStore(tmp_path / "taught.sqlite")
    store.add("Höhle", "NOUN", WordState.TAUGHT)

    (result,) = add_sentences(
        store, checker, [SentenceToStore("Höhle", 3, "Die Höhle ist dunkel.")]
    )

    assert result.status == "stored"


def test_many_sentences_go_to_languagetool_in_one_request(checker, language_tool):
    sentences = [f"Das ist Satz {n}." for n in range(60)]
    sentences[41] = "Das ist falsch."

    problems = checker.check(sentences)

    assert len(language_tool.texts) == 1
    assert problems[41] == ["Fehler: falsch"]
    assert [p for n, p in enumerate(problems) if n != 41] == [[]] * 59


def test_problems_go_to_the_right_sentence_after_characters_outside_the_bmp(checker):
    smileys = "\U0001F600" * 20  # 2 UTF-16 code units each
    problems = checker.check([f"Gut {smileys}.", "falsch.", "Gut so."])

    assert problems == [[], ["Fehler: falsch"], []]


def test_style_hints_are_not_problems(clock):
    language_tool = FakeLanguageTool(style_words=["Er"])
    checker = SentenceChecker(language_tool, clock)

    assert checker.check(["Er geht.", "Er kommt.", "Er bleibt."]) == [[], [], []]


def test_a_text_too_big_for_one_request_is_split_over_several(language_tool, clock):
    checker = SentenceChecker(language_tool, clock, max_request_bytes=100)
    sentences = [f"Das ist der lange Satz Nummer {n}." for n in range(10)]

    problems = checker.check(sentences)

    assert len(language_tool.texts) > 1
    assert all(len(text.encode("utf-8")) <= 100 for text in language_tool.texts)
    assert "\n\n".join(language_tool.texts) == "\n\n".join(sentences)
    assert problems == [[]] * 10


def test_requests_wait_to_stay_under_the_rate_limit(language_tool, clock):
    checker = SentenceChecker(language_tool, clock, max_requests_per_minute=2)

    for _ in range(3):
        checker.check(["Das ist gut."])

    assert len(language_tool.texts) == 3
    assert clock.sleeps == [60]


def test_requests_wait_to_stay_under_the_bytes_per_minute_limit(language_tool, clock):
    checker = SentenceChecker(
        language_tool, clock, max_request_bytes=50, max_bytes_per_minute=100
    )
    sentence = "x" * 40

    checker.check([sentence, sentence, sentence])

    assert len(language_tool.texts) == 3
    assert clock.sleeps == [60]


def test_requests_after_a_quiet_minute_do_not_wait(language_tool, clock):
    checker = SentenceChecker(language_tool, clock, max_requests_per_minute=2)
    checker.check(["Das ist gut."])
    checker.check(["Das ist gut."])

    clock.time += 61
    checker.check(["Das ist gut."])

    assert clock.sleeps == []


class BusyOnce(FakeLanguageTool):
    """Answers "too many requests" for the first `busy` requests."""

    def __init__(self, busy: int):
        super().__init__()
        self.busy = busy

    def check(self, text):
        if self.busy:
            self.busy -= 1
            raise LanguageToolBusy("too many requests")
        return super().check(text)


def test_a_busy_languagetool_is_asked_again_after_a_minute(clock):
    checker = SentenceChecker(BusyOnce(busy=1), clock)

    assert checker.check(["Das ist falsch."]) == [["Fehler: falsch"]]
    assert clock.sleeps == [60]


def test_languagetool_busy_twice_in_a_row_is_an_error(clock):
    checker = SentenceChecker(BusyOnce(busy=2), clock)

    with pytest.raises(LanguageToolBusy):
        checker.check(["Das ist gut."])
