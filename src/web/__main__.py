"""Start the exercise page: python -m web --episode Dark/S01E03"""

import argparse
import threading
import webbrowser
from pathlib import Path
from urllib.parse import quote

import uvicorn

from core.episode import DEFAULT_MEDIA_ROOT
from core.vocab_store import DEFAULT_DB
from web.server import create_app

parser = argparse.ArgumentParser(prog="python -m web")
parser.add_argument("--episode", help='for example "Dark/S01E03"')
parser.add_argument("--media-root", type=Path, default=DEFAULT_MEDIA_ROOT)
parser.add_argument("--db", type=Path, default=DEFAULT_DB)
parser.add_argument("--port", type=int, default=8000)
parser.add_argument(
    "--no-browser", action="store_true", help="only start the web server"
)
args = parser.parse_args()

if not args.no_browser:
    url = f"http://127.0.0.1:{args.port}/"
    if args.episode:
        url += f"?episode={quote(args.episode)}"
    threading.Timer(1.0, webbrowser.open, [url]).start()
uvicorn.run(create_app(args.media_root, args.db), host="127.0.0.1", port=args.port)
