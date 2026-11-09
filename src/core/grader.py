"""The grader: feedback on open answers of a Lesson.

Open answers are own sentences, translations and "explain why" answers. No
script can compare them with one correct answer. A headless grader agent
checks them; the grader runner is the adapter that starts it. The grader
gets only the exercise, the answer and the correct answer, never the learner
state. It replies with JSON in the result shape of the script checks.

The cheapest checker goes first: LanguageTool checks an own sentence, and
only a sentence with no problems goes to the grader, which checks that it
does the task.
"""

import json
import re
import threading
from typing import Protocol

from core.lesson import OpenKind
from core.results import Result
from core.sentences import SentenceChecker

MAX_ANSWER_LENGTH = 500
# The problems of an own sentence the reason shows; more make it long.
_MAX_PROBLEMS = 2
_FENCE = re.compile(r"\A```(?:json)?\s*(.*?)\s*```\Z", re.DOTALL)


class GraderError(ValueError):
    """The grader could not check an answer. The answer is not saved."""


class GraderRunner(Protocol):
    def run(self, prompt: str) -> str:
        """Give the prompt to the grader agent; give its reply.

        Raises GraderError when the grader cannot run.
        """


class Grader:
    """Checks open answers: LanguageTool first where it can, then the grader."""

    def __init__(self, runner: GraderRunner, checker: SentenceChecker | None = None):
        self._runner = runner
        self._checker = checker
        # The web server checks answers in more than one thread; the checker
        # counts its requests for the rate limit, one check at a time.
        self._checker_lock = threading.Lock()

    def check(self, exercise: dict, answer: str) -> Result:
        """The result of an open answer to a Lesson exercise.

        An own sentence that LanguageTool finds problems in is wrong: the
        grader is not needed. When LanguageTool cannot check it, the grader
        checks it alone. An empty or too long answer is rejected.
        """
        answer = answer.strip()
        if not answer:
            raise ValueError("Write an answer")
        if len(answer) > MAX_ANSWER_LENGTH:
            raise ValueError(
                f"The answer is too long; use at most {MAX_ANSWER_LENGTH} characters"
            )
        if exercise["kind"] == OpenKind.SENTENCE.value and self._checker is not None:
            problems = self._language_tool_problems(answer)
            if problems:
                return Result(
                    False, exercise["answer"], "; ".join(problems[:_MAX_PROBLEMS])
                )
        prompt = json.dumps(
            {
                "exercise": {
                    "kind": exercise["kind"],
                    "task": exercise["sentence"],
                    "explanation": exercise["explanation"],
                },
                "answer": answer,
                "correct_answer": exercise["answer"],
            },
            ensure_ascii=False,
        )
        result = _result(self._runner.run(prompt))
        # Script checks always give a correction; so does the grader.
        return Result(result.right, result.correction or exercise["answer"], result.reason)


    def _language_tool_problems(self, answer: str) -> list[str]:
        try:
            with self._checker_lock:
                (problems,) = self._checker.check([answer])
        except ValueError:
            return []  # LanguageTool cannot check it now; the grader can.
        return problems


def _result(reply: str) -> Result:
    """The grader's reply as a result; GraderError if it has the wrong shape."""
    text = reply.strip()
    fenced = _FENCE.match(text)
    if fenced:
        text = fenced.group(1)
    try:
        found = json.loads(text)
    except json.JSONDecodeError as error:
        raise GraderError(f"The reply of the grader is not JSON: {error}") from error
    if (
        not isinstance(found, dict)
        or not isinstance(found.get("right"), bool)
        or not isinstance(found.get("correction"), str)
        or not isinstance(found.get("reason"), str)
    ):
        raise GraderError(
            'The reply of the grader does not have the shape {"right": true or '
            'false, "correction": "...", "reason": "..."}'
        )
    return Result(found["right"], found["correction"].strip(), found["reason"].strip())
