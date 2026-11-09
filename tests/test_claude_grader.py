"""The grader runner: starts Claude Code headless with the grader agent."""

import json
import subprocess

import pytest

from core import GraderError
from core.claude_grader import ClaudeGrader

SCHEMA_KEYS = {"right", "correction", "reason"}


class FakeProcess:
    """Stands in for the claude program: keeps each call, gives a fixed output."""

    def __init__(self, returncode=0, stdout="", stderr="", error=None):
        self.returncode, self.stdout, self.stderr, self.error = (
            returncode, stdout, stderr, error,
        )
        self.calls = []

    def __call__(self, command, stdin, env, timeout):
        self.calls.append({"command": command, "stdin": stdin, "env": env, "timeout": timeout})
        if self.error:
            raise self.error
        return self.returncode, self.stdout, self.stderr


def envelope(**fields):
    return json.dumps({"type": "result", "subtype": "success", "is_error": False, **fields})


GRADED = {"right": True, "correction": "Ich helfe dem Kind.", "reason": "Right."}


def test_the_grader_runs_headless_with_the_grader_agent_no_tools_and_the_prompt_on_stdin():
    process = FakeProcess(stdout=envelope(result="", structured_output=GRADED))

    ClaudeGrader(executable="claude", process=process).run('{"answer": "Ich helfe"}')

    (call,) = process.calls
    command = call["command"]
    assert command[:4] == ["claude", "-p", "--agent", "grader"]
    assert command[command.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in command
    assert "--no-session-persistence" in command
    assert command[command.index("--output-format") + 1] == "json"
    schema = json.loads(command[command.index("--json-schema") + 1])
    assert set(schema["required"]) == SCHEMA_KEYS
    assert call["stdin"] == '{"answer": "Ich helfe"}'


def test_the_structured_output_is_the_reply():
    process = FakeProcess(stdout=envelope(result="Done.", structured_output=GRADED))

    reply = ClaudeGrader(executable="claude", process=process).run("{}")

    assert json.loads(reply) == GRADED


def test_without_structured_output_the_result_text_is_the_reply():
    process = FakeProcess(stdout=envelope(result=json.dumps(GRADED)))

    reply = ClaudeGrader(executable="claude", process=process).run("{}")

    assert json.loads(reply) == GRADED


def test_the_grader_does_not_run_as_a_nested_session_of_the_tutor(monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("GRADER_TEST_KEEP", "yes")
    process = FakeProcess(stdout=envelope(structured_output=GRADED))

    ClaudeGrader(executable="claude", process=process).run("{}")

    env = process.calls[0]["env"]
    assert "CLAUDECODE" not in env
    assert env["GRADER_TEST_KEEP"] == "yes"


@pytest.mark.parametrize(
    "process, problem",
    [
        (FakeProcess(returncode=1, stderr="Not logged in"), "Not logged in"),
        (FakeProcess(stdout=envelope(is_error=True, result="Usage limit reached")), "Usage limit"),
        (FakeProcess(stdout="not json"), "not understood"),
        (FakeProcess(error=FileNotFoundError("claude")), "cannot be started"),
        (FakeProcess(error=subprocess.TimeoutExpired("claude", 120)), "took too long"),
    ],
    ids=["exit code", "error result", "bad output", "no claude", "timeout"],
)
def test_a_grader_run_that_fails_is_a_grader_error(process, problem):
    with pytest.raises(GraderError, match=problem):
        ClaudeGrader(executable="claude", process=process).run("{}")
