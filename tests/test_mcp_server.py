"""Smoke test: talk MCP to the real server process, as Claude Code does."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from core import VocabStore, WordState

ROOT = Path(__file__).parents[1]
MEDIA = Path(__file__).parent / "fixtures"


class Client:
    def __init__(self, db: Path):
        self._process = subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "scripts" / "mcp_server.py"),
                "--media-root",
                str(MEDIA),
                "--db",
                str(db),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        self._next_id = 0

    def send(self, message: dict) -> None:
        self._process.stdin.write(json.dumps(message).encode("utf-8") + b"\n")
        self._process.stdin.flush()

    def request(self, method: str, params: dict | list | None = None) -> dict:
        self._next_id += 1
        self.send({"jsonrpc": "2.0", "id": self._next_id, "method": method,
                   "params": {} if params is None else params})
        reply = json.loads(self._process.stdout.readline().decode("utf-8"))
        assert reply["id"] == self._next_id
        return reply

    def call_tool(self, name: str, arguments: dict) -> dict:
        return self.request("tools/call", {"name": name, "arguments": arguments})[
            "result"
        ]

    def close(self) -> int:
        self._process.stdin.close()
        return self._process.wait(timeout=10)


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    return tmp_path_factory.mktemp("data") / "vocab.sqlite"


@pytest.fixture(scope="module")
def client(db):
    client = Client(db)
    client.request(
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0"},
        },
    )
    client.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    yield client
    client.close()


def test_initialize_names_the_server_and_offers_tools(tmp_path):
    client = Client(tmp_path / "vocab.sqlite")

    reply = client.request(
        "initialize",
        {"protocolVersion": "2025-06-18", "capabilities": {},
         "clientInfo": {"name": "test", "version": "0"}},
    )

    assert reply["result"]["protocolVersion"] == "2025-06-18"
    assert "tools" in reply["result"]["capabilities"]
    assert reply["result"]["serverInfo"]["name"]
    assert client.close() == 0


def test_tools_list_gives_each_tool_with_its_input_schema(client):
    tools = client.request("tools/list")["result"]["tools"]

    by_name = {tool["name"]: tool for tool in tools}
    assert {"parse_subtitles", "split_words", "vocab_lookup", "new_words"} <= set(
        by_name
    )
    assert by_name["new_words"]["inputSchema"]["required"] == ["episode"]


def test_the_tutor_can_process_an_episode_and_report_its_new_words(client, db):
    VocabStore(db).add("Polizei", "NOUN", WordState.KNOWN)

    result = client.call_tool("new_words", {"episode": "Dark/S01E01"})

    assert result["isError"] is False
    words = json.loads(result["content"][0]["text"])
    assert {"base_form": "aufgeben", "word_type": "VERB"} in words
    assert {"base_form": "Polizei", "word_type": "NOUN"} not in words
    assert "Höhle" in result["content"][0]["text"]


def test_a_failed_tool_call_is_a_tool_result_with_is_error(client):
    result = client.call_tool("new_words", {"episode": "Dark/S09E09"})

    assert result["isError"] is True
    assert "No Episode" in result["content"][0]["text"]


def test_an_unknown_method_is_a_json_rpc_error(client):
    reply = client.request("resources/list")

    assert reply["error"]["code"] == -32601


def test_a_request_with_params_that_are_not_an_object_is_an_error_and_the_server_goes_on(
    client,
):
    reply = client.request("tools/call", ["new_words"])

    assert reply["error"]["code"] == -32602
    assert client.request("ping")["result"] == {}
