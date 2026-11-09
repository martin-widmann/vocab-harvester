"""The grader runner adapter: one headless Claude Code run per open answer.

It starts `claude -p --agent grader` with the user's own Claude Code login,
not the API. The grader agent gets no tools and no MCP servers: it only
reads the prompt and replies with the result JSON.
"""

import json
import os
import shutil
import subprocess
from collections.abc import Callable

from core.grader import GraderError

AGENT = "grader"
TIMEOUT = 180
# The JSON the grader must reply with: the result shape of the script checks.
RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "right": {"type": "boolean"},
        "correction": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["right", "correction", "reason"],
    "additionalProperties": False,
}
# Claude Code refuses to start inside another Claude Code session. The web
# server may be started from the tutor's session, but the grader is its own
# process, not a nested session.
_SESSION_VARIABLES = {"CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SESSION_ID"}
# Keep claude from opening a console window when started on Windows.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# (command, stdin, environment, timeout) -> (exit code, stdout, stderr)
Process = Callable[[list[str], str, dict[str, str], float], tuple[int, str, str]]


def _process(
    command: list[str], stdin: str, env: dict[str, str], timeout: float
) -> tuple[int, str, str]:
    done = subprocess.run(
        command,
        input=stdin,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=timeout,
        creationflags=_NO_WINDOW,
    )
    return done.returncode, done.stdout, done.stderr


class ClaudeGrader:
    """Runs the grader agent of this plugin headless, once per prompt."""

    def __init__(
        self,
        executable: str | None = None,
        process: Process = _process,
        timeout: float = TIMEOUT,
    ):
        # On Windows "claude" may be claude.cmd, which needs its full path.
        self._executable = executable or shutil.which("claude") or "claude"
        self._process = process
        self._timeout = timeout

    def run(self, prompt: str) -> str:
        command = [
            self._executable,
            "-p",
            "--agent",
            AGENT,
            "--tools",
            "",
            "--strict-mcp-config",
            "--no-session-persistence",
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(RESULT_SCHEMA),
        ]
        env = {
            name: value
            for name, value in os.environ.items()
            if name not in _SESSION_VARIABLES
        }
        try:
            code, stdout, stderr = self._process(command, prompt, env, self._timeout)
        except subprocess.TimeoutExpired as error:
            raise GraderError(
                f"The grader took too long (more than {self._timeout:.0f} seconds); "
                "try again"
            ) from error
        except OSError as error:
            raise GraderError(
                f"The grader cannot be started: is Claude Code installed? ({error})"
            ) from error
        if code != 0:
            problem = (stderr or stdout).strip() or f"exit code {code}"
            raise GraderError(f"The grader did not run: {problem}")
        try:
            output = json.loads(stdout)
            if not isinstance(output, dict):
                raise ValueError("not a JSON object")
        except ValueError as error:
            raise GraderError(
                f"The output of the grader is not understood: {error}"
            ) from error
        if output.get("is_error"):
            raise GraderError(f"The grader did not run: {output.get('result', '')}")
        structured = output.get("structured_output")
        if isinstance(structured, dict):
            return json.dumps(structured, ensure_ascii=False)
        result = output.get("result")
        if not isinstance(result, str):
            raise GraderError("The output of the grader is not understood: no result")
        return result
