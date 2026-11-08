"""Run the data guard hook. The plugin's PreToolUse hook runs this file."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_guard import main  # noqa: E402

main()
