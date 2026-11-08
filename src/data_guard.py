"""Data guard: a hook that blocks direct writes to the data files.

Agents change data only through the MCP tools. Claude Code runs this before
each file-writing or shell tool. It imports nothing from the core, so it is
fast enough to run before every tool call.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# The file tools that write, with the input field that holds the path.
FILE_TOOLS = {
    "Write": "file_path",
    "Edit": "file_path",
    "MultiEdit": "file_path",
    "NotebookEdit": "notebook_path",
}
SHELL_TOOLS = {"Bash", "PowerShell"}

# The parts of a shell command that can be a path.
_PATH_LIKE = re.compile(r"[^\s\"'`;|&<>()=,]+")

REASON = (
    "{path} is a data file. Data files change only through an MCP tool of "
    "the german-media-learning plugin, never by a direct write."
)


def blocked_reason(event: dict, data_dir: Path, media_root: Path) -> str | None:
    """Why this tool call must be blocked, or None if it may go ahead."""
    tool = event.get("tool_name")
    tool_input = event.get("tool_input") or {}
    cwd = Path(event.get("cwd") or ".")
    if tool in FILE_TOOLS:
        candidates = [str(tool_input.get(FILE_TOOLS[tool]) or "")]
    elif tool in SHELL_TOOLS:
        candidates = _PATH_LIKE.findall(str(tool_input.get("command") or ""))
    else:
        return None
    for candidate in candidates:
        if candidate and _is_data_file(cwd, candidate, data_dir, media_root):
            return REASON.format(path=candidate)
    return None


def _is_data_file(cwd: Path, candidate: str, data_dir: Path, media_root: Path) -> bool:
    try:
        path = (cwd / candidate.replace("\\", "/")).resolve()
    except (OSError, ValueError):
        return False
    if path.is_relative_to(data_dir.resolve()):
        return True
    return path.is_relative_to(media_root.resolve()) and path.name.endswith(
        ".tagged.srt"
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="data_guard")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--media-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        print(f"data guard: hook input is not JSON: {error}", file=sys.stderr)
        sys.exit(1)  # A non-blocking error: Claude Code shows it and goes on.
    reason = blocked_reason(event, args.data_dir, args.media_root)
    if reason is not None:
        print(reason, file=sys.stderr)
        sys.exit(2)  # Exit code 2 blocks the tool call.
