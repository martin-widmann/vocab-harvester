"""The plugin files: manifest, agents and skills fit together with the code."""

import json
import re
import shlex
from pathlib import Path

import pytest

from core.episode import DEFAULT_MEDIA_ROOT
from core.vocab_store import DEFAULT_DB
from mcp_server.tools import Toolbox

ROOT = Path(__file__).parents[1]
MANIFEST = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text("utf-8"))
PLUGIN = MANIFEST["name"]
AGENTS = sorted((ROOT / "agents").glob("*.md"))
TOOL_NAMES = set(Toolbox(".", "unused.sqlite", page=None).tools)


def frontmatter(path: Path) -> dict[str, str]:
    match = re.match(r"---\n(.*?)\n---\n", path.read_text("utf-8"), re.DOTALL)
    assert match, f"{path.name} has no frontmatter"
    fields = {}
    for row in match.group(1).splitlines():
        key, _, value = row.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def plugin_path(argument: str) -> Path:
    return Path(argument.replace("${CLAUDE_PLUGIN_ROOT}", str(ROOT))).resolve()


def test_the_mcp_server_is_declared_at_plugin_level_and_runs_the_server_script():
    servers = MANIFEST["mcpServers"]

    assert list(servers) == ["learning"]
    assert plugin_path(servers["learning"]["args"][-1]) == (
        ROOT / "scripts" / "mcp_server.py"
    ).resolve()


def test_the_data_guard_hook_is_declared_at_plugin_level_for_every_writing_tool():
    (entry,) = MANIFEST["hooks"]["PreToolUse"]

    assert set(entry["matcher"].split("|")) == {
        "Write", "Edit", "MultiEdit", "NotebookEdit", "Bash", "PowerShell",
    }
    (hook,) = entry["hooks"]
    assert hook["type"] == "command"


def test_the_hook_guards_the_same_folders_the_core_uses():
    (hook,) = MANIFEST["hooks"]["PreToolUse"][0]["hooks"]
    words = shlex.split(hook["command"])

    assert plugin_path(words[1]) == (ROOT / "scripts" / "data_guard.py").resolve()
    assert plugin_path(words[words.index("--data-dir") + 1]) == DEFAULT_DB.parent
    assert plugin_path(words[words.index("--media-root") + 1]) == DEFAULT_MEDIA_ROOT


def test_the_local_marketplace_offers_this_folder_as_the_plugin():
    marketplace = json.loads(
        (ROOT / ".claude-plugin" / "marketplace.json").read_text("utf-8")
    )

    (entry,) = marketplace["plugins"]
    assert entry["name"] == PLUGIN
    assert entry["source"] == "./"


def test_there_is_a_tutor_agent():
    assert "tutor" in [frontmatter(path)["name"] for path in AGENTS]


@pytest.mark.parametrize("agent", AGENTS, ids=lambda path: path.stem)
def test_every_agent_uses_model_inherit(agent):
    assert frontmatter(agent)["model"] == "inherit"


@pytest.mark.parametrize("agent", AGENTS, ids=lambda path: path.stem)
def test_no_agent_declares_fields_that_plugin_subagents_ignore(agent):
    assert not {"hooks", "mcpServers", "permissionMode"} & set(frontmatter(agent))


def tools_of(agent: str) -> set[str]:
    tools = frontmatter(ROOT / "agents" / f"{agent}.md")["tools"]
    return {tool.strip() for tool in tools.split(",")}


def mcp_tool(name: str) -> str:
    return f"mcp__plugin_{PLUGIN}_learning__{name}"


def test_the_tutor_has_only_the_plugin_tools_and_can_start_only_its_subagents():
    # Only the sentence-writer stores example sentences; only the topic-finder
    # reports Grammar topics and stores exercises.
    subagent_tools = {"add_sentences", "report_topics", "add_exercises"}
    assert tools_of("tutor") == {
        mcp_tool(name) for name in TOOL_NAMES - subagent_tools
    } | {f"Agent({PLUGIN}:sentence-writer)", f"Agent({PLUGIN}:topic-finder)"}


def test_there_is_a_sentence_writer_agent():
    assert frontmatter(ROOT / "agents" / "sentence-writer.md")["name"] == "sentence-writer"


def test_the_sentence_writer_stores_sentences_only_through_the_add_sentences_tool():
    tools = tools_of("sentence-writer")

    assert mcp_tool("add_sentences") in tools
    assert tools <= {mcp_tool(name) for name in TOOL_NAMES}


def test_there_is_a_topic_finder_agent():
    assert frontmatter(ROOT / "agents" / "topic-finder.md")["name"] == "topic-finder"


def test_the_topic_finder_reports_topics_and_stores_exercises_only_through_tools():
    tools = tools_of("topic-finder")

    assert {mcp_tool("report_topics"), mcp_tool("add_exercises")} <= tools
    assert tools <= {mcp_tool(name) for name in TOOL_NAMES}


def test_the_lesson_skill_opens_the_page_with_the_open_page_tool():
    skill = ROOT / "skills" / "lesson" / "SKILL.md"

    assert frontmatter(skill)["name"] == "lesson"
    assert f"mcp__plugin_{PLUGIN}_learning__open_page" in skill.read_text("utf-8")
