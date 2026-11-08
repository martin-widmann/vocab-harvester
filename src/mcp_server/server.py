"""The MCP protocol over stdio: one JSON-RPC message per line.

This is only the transport. Each tool call goes to the Toolbox, which calls
the core.
"""

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import BinaryIO

from core.episode import DEFAULT_MEDIA_ROOT
from core.vocab_store import DEFAULT_DB
from mcp_server.tools import ToolError, Toolbox
from web.launch import PageServer

SERVER_INFO = {"name": "german-media-learning", "version": "0.1.0"}
PROTOCOL_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"]

METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
PARSE_ERROR = -32700
INVALID_REQUEST = -32600


class _RpcError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def serve(toolbox: Toolbox, reader: BinaryIO, writer: BinaryIO) -> None:
    """Answer MCP requests until the reader is closed."""
    for raw in reader:
        if not raw.strip():
            continue
        reply = _answer(toolbox, raw)
        if reply is not None:
            writer.write(json.dumps(reply, ensure_ascii=False).encode("utf-8") + b"\n")
            writer.flush()


def _answer(toolbox: Toolbox, raw: bytes) -> dict | None:
    try:
        message = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return _error(None, PARSE_ERROR, f"Not valid JSON: {error}")
    if not isinstance(message, dict) or not isinstance(message.get("method"), str):
        return _error(None, INVALID_REQUEST, "Expected one JSON-RPC request object")
    if "id" not in message:
        return None  # A notification needs no answer.
    try:
        result = _handle(toolbox, message["method"], message.get("params") or {})
    except _RpcError as error:
        return _error(message["id"], error.code, str(error))
    return {"jsonrpc": "2.0", "id": message["id"], "result": result}


def _handle(toolbox: Toolbox, method: str, params: dict) -> dict:
    if method == "initialize":
        asked = params.get("protocolVersion")
        return {
            "protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }
    if method == "ping":
        return {}
    if method == "tools/list":
        return {
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.input_schema,
                }
                for tool in toolbox.tools.values()
            ]
        }
    if method == "tools/call":
        return _call_tool(toolbox, params)
    raise _RpcError(METHOD_NOT_FOUND, f"Unknown method {method!r}")


def _call_tool(toolbox: Toolbox, params: dict) -> dict:
    name = params.get("name")
    arguments = params.get("arguments") or {}
    if not isinstance(name, str) or not isinstance(arguments, dict):
        raise _RpcError(INVALID_PARAMS, "tools/call needs a name and an arguments object")
    try:
        text, failed = json.dumps(toolbox.call(name, arguments), ensure_ascii=False), False
    except ToolError as error:
        text, failed = str(error), True
    except Exception as error:  # A bug must not stop the server.
        traceback.print_exc(file=sys.stderr)
        text, failed = f"Internal error in {name}: {error}", True
    return {"content": [{"type": "text", "text": text}], "isError": failed}


def _error(request_id, code: int, message: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m mcp_server")
    parser.add_argument("--media-root", type=Path, default=DEFAULT_MEDIA_ROOT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--port", type=int, default=8000, help="of the web server")
    args = parser.parse_args(argv)

    reader, writer = sys.stdin.buffer, sys.stdout.buffer
    # Only protocol messages may go to stdout; any stray print goes to stderr.
    sys.stdout = sys.stderr
    page = PageServer(args.media_root, args.db, args.port)
    try:
        serve(Toolbox(args.media_root, args.db, page), reader, writer)
    finally:
        # The page runs only while the tutor session runs.
        page.close()
