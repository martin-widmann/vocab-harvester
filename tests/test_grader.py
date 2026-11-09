"""Open answers: own sentences, translations and "explain why" get feedback."""

import json

import pytest

from core import (
    Grader,
    GraderError,
    LessonFiles,
    Result,
    SentenceChecker,
    check_answer,
)
from fakes import FakeClock, FakeGraderRunner, FakeLanguageTool


def exercise(id, kind, sentence, answer, explanation, options=()):
    return {
        "id": id,
        "kind": kind,
        "sentence": sentence,
        "answer": answer,
        "options": list(options),
        "explanation": explanation,
    }


TRANSLATE = exercise(
    "dativ:1", "translate", "I am helping the child.", "Ich helfe dem Kind.",
    "helfen takes the dative.",
)
EXPLAIN = exercise(
    "dativ:2", "explain", "Wir danken der Lehrerin. Why is it der Lehrerin?",
    "danken takes a dative object, and the dative of die is der.",
    "danken takes the dative.",
)
OWN_SENTENCE = exercise(
    "dativ:3", "sentence", "Write your own sentence with helfen.",
    "Ich helfe meiner Schwester.", "helfen takes the dative.",
)
GAP = exercise("dativ:4", "gap", "Ich folge ___ Weg.", "dem", "folgen takes the dative.")

LESSON = {
    "schema_version": 1,
    "number": 1,
    "episode": "Test/S01E01",
    "sections": [
        {
            "number": 1,
            "words": [{"base_form": "suchen", "word_type": "VERB", "exercises": []}],
            "grammar": [
                {
                    "topic_id": "dativ",
                    "kind": "new",
                    "exercises": [TRANSLATE, EXPLAIN, OWN_SENTENCE, GAP],
                }
            ],
        }
    ],
}


def reply(right, correction, reason):
    return json.dumps({"right": right, "correction": correction, "reason": reason})


@pytest.fixture
def lessons(tmp_path):
    folder = tmp_path / "lessons"
    folder.mkdir()
    (folder / "lesson-001.json").write_text(json.dumps(LESSON), encoding="utf-8")
    return LessonFiles(folder)


@pytest.fixture
def language_tool():
    return FakeLanguageTool(bad_words=("helfe den",))


def grader_with(runner, language_tool):
    return Grader(runner, SentenceChecker(language_tool, FakeClock()))


def test_a_translation_is_checked_by_the_grader_and_gives_a_result(lessons, language_tool):
    runner = FakeGraderRunner(
        reply(False, "Ich helfe dem Kind.", "helfen takes the dative: dem Kind.")
    )

    result = check_answer(
        lessons, 1, "dativ:1", "Ich helfe das Kind.", grader=grader_with(runner, language_tool)
    )

    assert result == Result(
        right=False,
        correction="Ich helfe dem Kind.",
        reason="helfen takes the dative: dem Kind.",
    )


def test_the_grader_gets_only_the_exercise_the_answer_and_the_correct_answer(
    lessons, language_tool
):
    check_answer(lessons, 1, "dativ:4", "dem")  # An earlier answer: learner state.
    runner = FakeGraderRunner(reply(True, "Ich helfe dem Kind.", "Right: dem Kind."))

    check_answer(
        lessons, 1, "dativ:1", "Ich helfe dem Kind.", grader=grader_with(runner, language_tool)
    )

    (prompt,) = runner.prompts
    assert json.loads(prompt) == {
        "exercise": {
            "kind": "translate",
            "task": "I am helping the child.",
            "explanation": "helfen takes the dative.",
        },
        "answer": "Ich helfe dem Kind.",
        "correct_answer": "Ich helfe dem Kind.",
    }


def test_an_explain_why_answer_goes_to_the_grader(lessons, language_tool):
    runner = FakeGraderRunner(reply(True, "", "Yes: danken takes the dative."))

    result = check_answer(
        lessons, 1, "dativ:2", "Because danken needs the dative.",
        grader=grader_with(runner, language_tool),
    )

    assert result.right is True
    assert result.reason == "Yes: danken takes the dative."
    assert json.loads(runner.prompts[0])["exercise"]["kind"] == "explain"
    assert language_tool.texts == []


def test_an_empty_correction_of_the_grader_becomes_the_correct_answer(
    lessons, language_tool
):
    runner = FakeGraderRunner(reply(True, " ", "Right."))

    result = check_answer(
        lessons, 1, "dativ:1", "Ich helfe dem Kind.", grader=grader_with(runner, language_tool)
    )

    assert result.correction == "Ich helfe dem Kind."


def test_an_own_sentence_with_a_languagetool_problem_is_wrong_without_the_grader(
    lessons, language_tool
):
    runner = FakeGraderRunner()

    result = check_answer(
        lessons, 1, "dativ:3", "Ich helfe den Mann.", grader=grader_with(runner, language_tool)
    )

    assert language_tool.texts == ["Ich helfe den Mann."]
    assert runner.prompts == []
    assert result == Result(
        right=False,
        correction="Ich helfe meiner Schwester.",
        reason="Fehler: helfe den",
    )


def test_an_own_sentence_that_passes_languagetool_goes_to_the_grader(lessons, language_tool):
    runner = FakeGraderRunner(reply(False, "Ich helfe meiner Schwester.", "Use helfen."))

    result = check_answer(
        lessons, 1, "dativ:3", "Ich esse Brot.", grader=grader_with(runner, language_tool)
    )

    assert language_tool.texts == ["Ich esse Brot."]
    assert json.loads(runner.prompts[0])["answer"] == "Ich esse Brot."
    assert result == Result(False, "Ich helfe meiner Schwester.", "Use helfen.")


class UnreachableLanguageTool:
    def check(self, text):
        raise ValueError("LanguageTool cannot be reached")


def test_an_own_sentence_goes_to_the_grader_when_languagetool_cannot_be_reached(lessons):
    runner = FakeGraderRunner(reply(True, "Ich helfe dem Mann.", "Right."))

    result = check_answer(
        lessons, 1, "dativ:3", "Ich helfe dem Mann.",
        grader=grader_with(runner, UnreachableLanguageTool()),
    )

    assert result.right is True
    assert len(runner.prompts) == 1


@pytest.mark.parametrize(
    "bad_reply",
    [
        "Looks right to me!",
        json.dumps({"right": "yes", "correction": "", "reason": "Right."}),
        json.dumps({"right": True, "reason": "Right."}),
        json.dumps([True, "", "Right."]),
    ],
)
def test_a_grader_reply_in_the_wrong_shape_is_an_error_and_nothing_is_saved(
    lessons, language_tool, bad_reply
):
    runner = FakeGraderRunner(bad_reply)

    with pytest.raises(GraderError):
        check_answer(
            lessons, 1, "dativ:1", "Ich helfe dem Kind.",
            grader=grader_with(runner, language_tool),
        )
    assert lessons.results(1)["answers"] == {}


def test_a_grader_reply_in_a_json_code_block_is_read(lessons, language_tool):
    fenced = "```json\n" + reply(True, "Ich helfe dem Kind.", "Right.") + "\n```"
    runner = FakeGraderRunner(fenced)

    result = check_answer(
        lessons, 1, "dativ:1", "Ich helfe dem Kind.", grader=grader_with(runner, language_tool)
    )

    assert result == Result(True, "Ich helfe dem Kind.", "Right.")


def test_an_open_answer_and_its_result_are_saved_and_the_first_answer_stands(
    lessons, language_tool
):
    runner = FakeGraderRunner(reply(False, "Ich helfe dem Kind.", "dem Kind: dative."))
    grader = grader_with(runner, language_tool)

    first = check_answer(lessons, 1, "dativ:1", "Ich helfe das Kind.", grader=grader)
    again = check_answer(lessons, 1, "dativ:1", "Ich helfe dem Kind.", grader=grader)

    assert again == first
    assert len(runner.prompts) == 1
    assert lessons.results(1)["answers"] == {
        "dativ:1": {
            "answer": "Ich helfe das Kind.",
            "right": False,
            "correction": "Ich helfe dem Kind.",
            "reason": "dem Kind: dative.",
        }
    }


@pytest.mark.parametrize("answer", ["", "   ", "x" * 501])
def test_an_empty_or_too_long_open_answer_is_rejected_without_the_grader(
    lessons, language_tool, answer
):
    runner = FakeGraderRunner()

    with pytest.raises(ValueError):
        check_answer(lessons, 1, "dativ:1", answer, grader=grader_with(runner, language_tool))
    assert runner.prompts == []
    assert lessons.results(1)["answers"] == {}


def test_an_open_answer_needs_a_grader(lessons):
    with pytest.raises(ValueError, match="grader"):
        check_answer(lessons, 1, "dativ:1", "Ich helfe dem Kind.")


def test_a_finished_lesson_sends_no_open_answer_to_the_grader(lessons, language_tool):
    results = lessons.results(1)
    results["finished"] = True
    lessons.write_results(results)
    runner = FakeGraderRunner()

    with pytest.raises(ValueError, match="finished"):
        check_answer(
            lessons, 1, "dativ:1", "Ich helfe dem Kind.",
            grader=grader_with(runner, language_tool),
        )
    assert runner.prompts == []
