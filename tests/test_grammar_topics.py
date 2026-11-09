"""Grammar topics of an Episode and the exercise stock."""

from contextlib import closing
from datetime import timedelta

import pytest
from fakes import FakeClock, FakeLanguageTool

from core import (
    Curriculum,
    Exercise,
    ExerciseStatus,
    ExerciseStock,
    FoundTopic,
    Line,
    Refill,
    SentenceChecker,
    Topic,
    add_exercises,
    report_topics,
)

DRAFT = [
    Topic("dativ", "Dativ", "A2"),
    Topic("relativsatz", "Relativsatz", "B1"),
    Topic("passiv-modalverb", "Passiv mit Modalverb", "B2"),
    Topic("konjunktiv-1", "Konjunktiv I", "B2"),
]

LINES = [
    Line(number, timedelta(seconds=10 * number), timedelta(seconds=10 * number + 5), text)
    for number, text in [
        (1, "Ich helfe dem Mann."),
        (2, "Das muss gemacht werden."),
        (3, "Er sagte, er sei müde."),
        (4, "Das ist die Frau, die ich kenne."),
        (5, "Das kann repariert werden."),
    ]
]


@pytest.fixture
def path(tmp_path):
    return tmp_path / "vocab.sqlite"


@pytest.fixture
def curriculum(path):
    curriculum = Curriculum(path)
    curriculum.approve(curriculum.propose(DRAFT).number)
    yield curriculum
    curriculum.close()


@pytest.fixture
def language_tool():
    return FakeLanguageTool()


@pytest.fixture
def checker(language_tool):
    return SentenceChecker(language_tool, FakeClock())


@pytest.fixture
def stock(path):
    stock = ExerciseStock(path)
    yield stock
    stock.close()


def test_the_core_picks_1_new_topic_and_1_weak_point_with_the_lines_they_occur_in(
    curriculum, stock
):
    curriculum.review("dativ", passed=False)

    grammar = report_topics(
        curriculum,
        stock,
        "Dark/S01E01",
        LINES,
        [
            FoundTopic("dativ", [1]),
            FoundTopic("passiv-modalverb", [5, 2]),
            FoundTopic("konjunktiv-1", [3]),
        ],
    )

    assert grammar.new.topic == Topic("passiv-modalverb", "Passiv mit Modalverb", "B2")
    assert grammar.new.lines == [2, 5]
    assert grammar.weak.topic == Topic("dativ", "Dativ", "A2")
    assert grammar.weak.lines == [1]


def test_the_found_topics_are_kept_per_episode_and_a_new_report_replaces_them(
    curriculum, stock, path
):
    report_topics(curriculum, stock, "Dark/S01E01", LINES, [FoundTopic("dativ", [1])])
    report_topics(
        curriculum, stock, "Dark/S01E02", LINES, [FoundTopic("relativsatz", [4])]
    )
    report_topics(
        curriculum,
        stock,
        "Dark/S01E01",
        LINES,
        [FoundTopic("konjunktiv-1", [3]), FoundTopic("dativ", [1, 1])],
    )

    with closing(ExerciseStock(path)) as again:
        assert again.found_topics("Dark/S01E01") == [
            FoundTopic("konjunktiv-1", [3]),
            FoundTopic("dativ", [1]),
        ]
        assert again.found_topics("Dark/S01E02") == [FoundTopic("relativsatz", [4])]


@pytest.mark.parametrize(
    "found, problem",
    [
        ([FoundTopic("dativ", [9])], "no Line 9"),
        ([FoundTopic("dativ", [])], "needs the Lines"),
        ([FoundTopic("dativ", [1]), FoundTopic("dativ", [2])], "twice"),
        ([FoundTopic("Dativ Fall", [1])], "lowercase"),
    ],
    ids=["line not in episode", "no lines", "topic twice", "bad id"],
)
def test_a_malformed_report_is_rejected_and_not_kept(curriculum, stock, found, problem):
    report_topics(curriculum, stock, "Dark/S01E01", LINES, [FoundTopic("dativ", [1])])

    with pytest.raises(ValueError, match=problem):
        report_topics(curriculum, stock, "Dark/S01E01", LINES, found)

    assert stock.found_topics("Dark/S01E01") == [FoundTopic("dativ", [1])]


def test_topics_not_in_the_curriculum_are_kept_and_named(curriculum, stock):
    grammar = report_topics(
        curriculum, stock, "Dark/S01E01", LINES, [FoundTopic("futur-2", [3])]
    )

    assert (grammar.new, grammar.weak) == (None, None)
    assert grammar.not_in_curriculum == ["futur-2"]
    assert stock.found_topics("Dark/S01E01") == [FoundTopic("futur-2", [3])]


PASSIV = Topic("passiv-modalverb", "Passiv mit Modalverb", "B2")
DATIV = Topic("dativ", "Dativ", "A2")
FOUND = [FoundTopic("dativ", [1]), FoundTopic("passiv-modalverb", [2, 5])]


def passiv(n, verb="repariert"):
    """A gap exercise for the Passiv mit Modalverb topic."""
    return Exercise(
        "passiv-modalverb",
        "gap",
        f"Das Auto {n} muss heute noch {verb} ___.",
        "werden",
        [],
        "Modal verb + participle + werden.",
    )


def build(curriculum, stock, found=FOUND, episode="Dark/S01E01"):
    """A lesson build: the topic-finder reports the topics of an Episode."""
    return report_topics(curriculum, stock, episode, LINES, found)


def test_each_picked_topic_needs_5_exercises_for_an_empty_stock(curriculum, stock):
    curriculum.review("dativ", passed=False)

    grammar = build(curriculum, stock)

    assert grammar.refill == [Refill(PASSIV, 0, 5), Refill(DATIV, 0, 5)]


def test_exercises_that_pass_languagetool_are_stored_in_the_stock(
    curriculum, stock, checker, language_tool
):
    build(curriculum, stock)
    exercises = [passiv(n) for n in range(1, 6)]

    results = add_exercises(curriculum, stock, checker, exercises)

    assert [result.status for result in results] == [ExerciseStatus.STORED] * 5
    assert [stored.exercise for stored in stock.unused("passiv-modalverb")] == exercises
    # LanguageTool checks the sentence with the answer in the gap.
    assert "Das Auto 1 muss heute noch repariert werden." in language_tool.texts[0]


def test_a_failed_exercise_is_not_stored_and_the_topic_finder_writes_a_new_one(
    curriculum, stock, checker
):
    build(curriculum, stock)

    (result,) = add_exercises(curriculum, stock, checker, [passiv(1, "falsch")])

    assert result.status == ExerciseStatus.RETRY
    assert result.problems == ["Fehler: falsch"]
    assert result.retries_left == 14  # 3 tries for each of the 5 exercises needed
    assert stock.unused("passiv-modalverb") == []


def test_a_topic_that_failed_all_its_tries_stops_until_the_next_lesson_build(
    curriculum, stock, checker
):
    build(curriculum, stock)
    bad = [passiv(n, "falsch") for n in range(15)]
    for start in range(0, 15, 5):
        results = add_exercises(curriculum, stock, checker, bad[start : start + 5])

    assert results[-1].status == ExerciseStatus.STOPPED
    assert results[-1].retries_left == 0
    with pytest.raises(ValueError, match="next lesson build"):
        add_exercises(curriculum, stock, checker, [passiv(1)])

    build(curriculum, stock)
    (result,) = add_exercises(curriculum, stock, checker, [passiv(1)])
    assert result.status == ExerciseStatus.STORED


def test_a_low_stock_is_refilled_at_the_next_lesson_build(curriculum, stock, checker):
    build(curriculum, stock)
    add_exercises(curriculum, stock, checker, [passiv(n) for n in range(1, 6)])
    curriculum.taught("passiv-modalverb")
    used = stock.unused("passiv-modalverb")[:2]
    for stored in used:
        stock.mark_used(stored.id)

    # The next Episode does not have the topic, but its stock is low.
    grammar = build(
        curriculum, stock, [FoundTopic("konjunktiv-1", [3])], episode="Dark/S01E02"
    )

    assert grammar.refill == [
        Refill(Topic("konjunktiv-1", "Konjunktiv I", "B2"), 0, 5),
        Refill(PASSIV, 3, 2),
    ]
    add_exercises(curriculum, stock, checker, [passiv(n) for n in range(6, 8)])
    assert len(stock.unused("passiv-modalverb")) == 5
    assert used[0].id not in [s.id for s in stock.unused("passiv-modalverb")]


def test_a_full_stock_needs_no_refill(curriculum, stock, checker):
    build(curriculum, stock)
    add_exercises(curriculum, stock, checker, [passiv(n) for n in range(1, 6)])

    assert build(curriculum, stock).refill == []


def test_the_stock_takes_no_more_than_5_unused_exercises_per_topic(
    curriculum, stock, checker, language_tool
):
    build(curriculum, stock)
    add_exercises(curriculum, stock, checker, [passiv(n) for n in range(1, 4)])

    with pytest.raises(ValueError, match="room for 2"):
        add_exercises(curriculum, stock, checker, [passiv(n) for n in range(4, 7)])
    assert len(language_tool.texts) == 1


def test_only_topics_of_the_latest_lesson_build_take_exercises(
    curriculum, stock, checker
):
    build(curriculum, stock)
    dativ = Exercise("dativ", "gap", "Ich helfe ___ Mann.", "dem", [], "helfen + Dativ.")

    with pytest.raises(ValueError, match="not in the refill"):
        add_exercises(curriculum, stock, checker, [dativ])


def test_a_used_exercise_cannot_be_used_again(curriculum, stock, checker):
    build(curriculum, stock)
    add_exercises(curriculum, stock, checker, [passiv(1)])
    (stored,) = stock.unused("passiv-modalverb")
    stock.mark_used(stored.id)

    with pytest.raises(ValueError, match="not in the stock"):
        stock.mark_used(stored.id)


def choice(**changes):
    fields = dict(
        topic_id="passiv-modalverb",
        kind="choice",
        sentence="Der Brief muss heute ___ werden.",
        answer="geschrieben",
        options=["geschrieben", "schreiben", "schrieb"],
        explanation="Partizip II vor werden.",
    )
    return Exercise(**{**fields, **changes})


def test_a_choice_exercise_is_stored_with_its_options(curriculum, stock, checker):
    build(curriculum, stock)

    add_exercises(curriculum, stock, checker, [choice(answer=" geschrieben ")])

    (stored,) = stock.unused("passiv-modalverb")
    assert stored.exercise == choice()


@pytest.mark.parametrize(
    "bad, problem",
    [
        (choice(topic_id="futur-2"), "not in the Curriculum"),
        (choice(kind="translate"), "kind must be one of"),
        (choice(sentence="Der Brief muss heute geschrieben werden."), "exactly one gap"),
        (choice(sentence="Der ___ muss ___ werden."), "exactly one gap"),
        (choice(answer=""), "answer is empty"),
        (choice(answer="ge___"), "only the sentence"),
        (choice(explanation=" "), "explanation is empty"),
        (choice(sentence="Der Brief muss\n___ werden."), "one line"),
        (choice(sentence="Der Brief ___ " + "x" * 300), "too long"),
        (choice(options=["geschrieben"]), "2 to 4 options"),
        (choice(options=["schreiben", "schrieb"]), "one of the options"),
        (choice(options=["geschrieben", "geschrieben"]), "different"),
        (choice(kind="gap"), "no options"),
        (
            choice(
                sentence="Das Auto 1 muss heute noch repariert ___.",
                answer="werden",
                options=["werden", "wird"],
            ),
            "already",
        ),
    ],
)
def test_a_bad_exercise_rejects_the_whole_call_before_languagetool_runs(
    curriculum, stock, checker, language_tool, bad, problem
):
    build(curriculum, stock)
    add_exercises(curriculum, stock, checker, [passiv(1)])
    language_tool.texts.clear()

    with pytest.raises(ValueError, match=problem):
        add_exercises(curriculum, stock, checker, [passiv(2), bad])

    assert language_tool.texts == []
    assert len(stock.unused("passiv-modalverb")) == 1


def test_the_same_exercise_twice_in_one_call_is_rejected(curriculum, stock, checker):
    build(curriculum, stock)

    with pytest.raises(ValueError, match="already"):
        add_exercises(curriculum, stock, checker, [passiv(1), passiv(1)])
