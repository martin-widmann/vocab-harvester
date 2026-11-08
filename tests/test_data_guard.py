import json
import subprocess
import sys
from pathlib import Path

import pytest

from data_guard import blocked_reason

ROOT = Path(__file__).parents[1]


@pytest.fixture
def folders(tmp_path):
    data, media = tmp_path / "data", tmp_path / "media"
    (media / "Dark" / "S01E01").mkdir(parents=True)
    data.mkdir()
    return tmp_path, data, media


def event(tool_name, cwd, **tool_input):
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": tool_input,
        "cwd": str(cwd),
    }


def reason(folders, tool_name, **tool_input):
    root, data, media = folders
    return blocked_reason(event(tool_name, root, **tool_input), data, media)


@pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit"])
def test_a_file_tool_may_not_write_into_the_data_folder(folders, tool):
    _, data, _ = folders

    assert reason(folders, tool, file_path=str(data / "vocab.sqlite"))


def test_a_relative_path_into_the_data_folder_is_blocked_too(folders):
    assert reason(folders, "Write", file_path="data/lessons/lesson-001.json")


def test_a_path_that_climbs_back_into_the_data_folder_is_blocked(folders):
    assert reason(folders, "Edit", file_path="src/../data/vocab.sqlite")


def test_a_notebook_in_the_data_folder_is_blocked(folders):
    assert reason(folders, "NotebookEdit", notebook_path="data/notes.ipynb")


def test_a_tagged_subtitle_file_in_the_media_folder_is_blocked(folders):
    _, _, media = folders
    tagged = media / "Dark" / "S01E01" / "Dark.S01E01.de.tagged.srt"

    assert reason(folders, "Write", file_path=str(tagged))


@pytest.mark.parametrize("path", ["src/core/episode.py", "notes.md", "database.py"])
def test_other_files_may_be_written(folders, path):
    assert reason(folders, "Write", file_path=path) is None


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
@pytest.mark.parametrize(
    "command",
    [
        "sqlite3 data/vocab.sqlite \"DELETE FROM words\"",
        "echo x > ./data/vocab.sqlite",
        "rm -rf data",
        "Remove-Item -Recurse 'data\\lessons'",
    ],
)
def test_a_shell_command_that_names_a_data_file_is_blocked(folders, tool, command):
    assert reason(folders, tool, command=command)


def test_a_shell_command_with_the_absolute_data_path_is_blocked(folders):
    _, data, _ = folders

    assert reason(folders, "Bash", command=f'cp x.sqlite "{data}\\vocab.sqlite"')


@pytest.mark.parametrize(
    "command", ["python -m pytest -q", "git status", "ls src/core", "grep -r metadata src"]
)
def test_other_shell_commands_are_not_blocked(folders, command):
    assert reason(folders, "Bash", command=command) is None


def test_tools_that_only_read_are_not_blocked(folders):
    assert reason(folders, "Read", file_path="data/vocab.sqlite") is None


def test_the_hook_script_blocks_with_exit_code_2_and_a_reason(folders):
    root, data, media = folders
    hook = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "data_guard.py"),
         "--data-dir", str(data), "--media-root", str(media)],
        input=json.dumps(event("Write", root, file_path="data/vocab.sqlite")),
        capture_output=True,
        text=True,
    )

    assert hook.returncode == 2
    assert "MCP tool" in hook.stderr


def test_the_hook_script_allows_other_writes_with_exit_code_0(folders):
    root, data, media = folders
    hook = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "data_guard.py"),
         "--data-dir", str(data), "--media-root", str(media)],
        input=json.dumps(event("Write", root, file_path="notes.md")),
        capture_output=True,
        text=True,
    )

    assert hook.returncode == 0


@pytest.mark.skipif(sys.platform != "win32", reason="Git Bash drive paths")
def test_a_git_bash_drive_path_to_the_data_folder_is_blocked(folders):
    _, data, _ = folders
    drive, rest = str(data).split(":", 1)
    bash_path = f"/{drive.lower()}{rest}".replace("\\", "/")

    assert reason(folders, "Bash", command=f"rm {bash_path}/vocab.sqlite")


@pytest.mark.parametrize("tool_input", [None, "data/vocab.sqlite", ["data"]])
def test_a_tool_input_that_is_not_an_object_does_not_crash_the_guard(folders, tool_input):
    root, data, media = folders
    broken = {"tool_name": "Write", "tool_input": tool_input, "cwd": str(root)}

    assert blocked_reason(broken, data, media) is None
