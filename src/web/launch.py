"""Start the web server in its own process and open the exercise page."""

import json
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import webbrowser
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote

from core import find_episode
from web.server import APP_TITLE

SRC = Path(__file__).resolve().parents[1]
START_TIMEOUT = 60.0


class PageError(RuntimeError):
    """The page cannot be opened, for example because the port is in use."""


class PageServer:
    """The exercise page. It starts the web server once and stops it on close."""

    def __init__(
        self,
        media_root: Path | str,
        db_path: Path | str,
        port: int = 8000,
        open_browser: Callable[[str], object] = webbrowser.open,
    ):
        self._media_root = Path(media_root).resolve()
        self._db_path = Path(db_path).resolve()
        self._port = port
        self._open_browser = open_browser
        self._process: subprocess.Popen | None = None

    def open(self, episode: str) -> str:
        """Open the page of an Episode; start the web server if it is not running."""
        find_episode(self._media_root, episode)
        state = self._probe()
        if state == "other":
            raise PageError(f"Port {self._port} is used by another program")
        if state == "free":
            self._start()
        url = f"http://127.0.0.1:{self._port}/?episode={quote(episode)}"
        self._open_browser(url)
        return url

    def close(self) -> None:
        """Stop the web server if this PageServer started it."""
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
        self._process = None

    def _start(self) -> None:
        # The server's own error output, to explain a failed start. A file and
        # not a pipe: a full pipe would block the server.
        with tempfile.TemporaryFile() as errors:
            self._spawn(errors)

    def _spawn(self, errors) -> None:
        self._process = subprocess.Popen(
            [
                sys.executable, "-m", "web",
                "--media-root", str(self._media_root),
                "--db", str(self._db_path),
                "--port", str(self._port),
                "--no-browser",
            ],
            cwd=SRC,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=errors,
        )
        deadline = time.monotonic() + START_TIMEOUT
        while time.monotonic() < deadline:
            code = self._process.poll()
            if code is not None:
                self._process = None
                raise PageError(
                    f"The web server stopped at start (exit code {code}): "
                    + _tail(errors)
                )
            if self._probe() == "ours":
                return
            time.sleep(0.2)
        self.close()
        raise PageError(f"The web server did not start in {START_TIMEOUT:.0f} s")

    def _probe(self) -> str:
        """"free", "ours" if the web server listens, or "other" for another program."""
        # A connect and not a bind: on Windows a bind to 127.0.0.1 succeeds
        # even when another program listens on all addresses (0.0.0.0).
        try:
            socket.create_connection(("127.0.0.1", self._port), timeout=2).close()
        except OSError:
            return "free"  # Nothing listens on the port.
        url = f"http://127.0.0.1:{self._port}/openapi.json"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                title = json.loads(response.read().decode("utf-8"))["info"]["title"]
        except (OSError, ValueError, KeyError, TypeError):
            return "other"
        return "ours" if title == APP_TITLE else "other"


def _tail(errors) -> str:
    errors.seek(0)
    return errors.read()[-2000:].decode("utf-8", "replace").strip()
