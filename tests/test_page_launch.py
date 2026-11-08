"""The page launcher starts the real web server process and opens the page."""

import json
import socket
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from web.launch import PageError, PageServer

MEDIA = Path(__file__).parent / "fixtures"


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def get_json(url: str):
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


class Browser:
    def __init__(self):
        self.opened: list[str] = []

    def __call__(self, url: str) -> None:
        self.opened.append(url)


@pytest.fixture
def port():
    return free_port()


@pytest.fixture
def browser():
    return Browser()


@pytest.fixture
def page(tmp_path, port, browser):
    page = PageServer(MEDIA, tmp_path / "vocab.sqlite", port, open_browser=browser)
    yield page
    page.close()


def test_open_starts_the_web_server_and_opens_the_check_page_of_the_episode(
    page, port, browser
):
    url = page.open("Dark/S01E01")

    assert url == f"http://127.0.0.1:{port}/?episode=Dark/S01E01"
    assert browser.opened == [url]
    words = get_json(f"http://127.0.0.1:{port}/api/check?episode=Dark/S01E01")
    assert {"base_form": "aufgeben", "word_type": "VERB"} in words


def test_a_second_open_uses_the_server_that_already_runs(
    tmp_path, page, port, browser
):
    page.open("Dark/S01E01")
    other = PageServer(MEDIA, tmp_path / "vocab.sqlite", port, open_browser=browser)

    url = other.open("Dark/S01E02")
    other.close()

    assert browser.opened[-1] == url
    assert get_json(f"http://127.0.0.1:{port}/api/check?episode=Dark/S01E02")


def test_close_stops_the_server_it_started(page, port):
    page.open("Dark/S01E01")

    page.close()

    with pytest.raises(OSError):
        get_json(f"http://127.0.0.1:{port}/api/check?episode=Dark/S01E01")


def test_an_unknown_episode_opens_nothing(page, browser):
    with pytest.raises(ValueError, match="No Episode"):
        page.open("Dark/S09E09")

    assert browser.opened == []


def test_a_port_used_by_another_program_is_an_error(page, port, browser):
    class NotOurServer(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(404)
            self.end_headers()

        def log_message(self, *args):
            pass

    other = HTTPServer(("127.0.0.1", port), NotOurServer)
    threading.Thread(target=other.serve_forever, daemon=True).start()
    try:
        with pytest.raises(PageError, match="another program"):
            page.open("Dark/S01E01")
    finally:
        other.shutdown()
        other.server_close()

    assert browser.opened == []


def test_a_program_that_listens_on_all_addresses_is_an_error(page, port, browser):
    other = socket.socket()
    other.bind(("0.0.0.0", port))
    other.listen()
    try:
        with pytest.raises(PageError, match="another program"):
            page.open("Dark/S01E01")
    finally:
        other.close()

    assert browser.opened == []
