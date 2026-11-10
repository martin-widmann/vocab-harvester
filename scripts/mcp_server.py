"""Start the MCP server. The plugin runs this file; it needs no install step."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcp_server.server import main  # noqa: E402

main()
