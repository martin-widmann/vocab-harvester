"""The page launcher starts the real web server process and opens the page."""

import json
import socket
import threading
import urllib.error
import urllib.request
from contextlib import closing
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from core import EpisodeLine, Teaching, VocabStore, WordState
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


def lesson_file(number: int, episode: str) -> dict:
    return {
        "schema_version": 1,
        "number": number,
        "episode": episode,
        "sections": [{"number": n, "words": [], "grammar": []} for n in (1, 2, 3)],
    }


def test_the_page_lists_the_lessons_newest_first_and_gives_each_lesson(
    tmp_path, page, port
):
    lessons = tmp_path / "lessons"
    lessons.mkdir()
    for number, episode in [(1, "Dark/S01E01"), (2, "Dark/S01E02")]:
        (lessons / f"lesson-00{number}.json").write_text(
            json.dumps(lesson_file(number, episode)), encoding="utf-8"
        )
    page.open("Dark/S01E01")

    assert get_json(f"http://127.0.0.1:{port}/api/lessons") == [
        {"number": 2, "episode": "Dark/S01E02"},
        {"number": 1, "episode": "Dark/S01E01"},
    ]
    assert get_json(f"http://127.0.0.1:{port}/api/lessons/1") == {
        **lesson_file(1, "Dark/S01E01"),
        "results": {},
        "finished": False,
    }
    with pytest.raises(urllib.error.HTTPError) as missing:
        get_json(f"http://127.0.0.1:{port}/api/lessons/9")
    assert missing.value.code == 404
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as response:
        assert 'id="lesson-tab"' in response.read().decode("utf-8")


def post_json(url: str, body: dict | None = None):
    request = urllib.request.Request(
        url,
        data=json.dumps(body or {}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def lesson_with_an_article_exercise() -> dict:
    lesson = lesson_file(1, "Dark/S01E01")
    lesson["sections"][0]["words"] = [
        {
            "base_form": "Höhle",
            "word_type": "NOUN",
            "exercises": [
                {
                    "id": "Höhle:article",
                    "kind": "article",
                    "sentence": "___ Höhle",
                    "answer": "die",
                    "options": ["der", "die", "das"],
                    "explanation": "Höhle is feminine: die Höhle.",
                }
            ],
        }
    ]
    return lesson


def test_the_page_checks_an_answer_and_finishes_the_lesson(tmp_path, page, port):
    lessons = tmp_path / "lessons"
    lessons.mkdir()
    (lessons / "lesson-001.json").write_text(
        json.dumps(lesson_with_an_article_exercise()), encoding="utf-8"
    )
    with closing(VocabStore(tmp_path / "vocab.sqlite")) as store:
        store.add("Höhle", "NOUN", WordState.UNKNOWN)
    page.open("Dark/S01E01")
    base = f"http://127.0.0.1:{port}/api/lessons/1"

    shown = get_json(base)["sections"][0]["words"][0]["exercises"][0]
    assert "answer" not in shown and "explanation" not in shown

    result = post_json(base + "/answers", {"exercise_id": "Höhle:article", "answer": "der"})
    assert result == {
        "right": False,
        "correction": "die Höhle",
        "reason": "Höhle is feminine: die Höhle.",
    }
    with pytest.raises(urllib.error.HTTPError) as rejected:
        post_json(base + "/answers", {"exercise_id": "Höhle:plural", "answer": "die"})
    assert rejected.value.code == 400

    assert post_json(base + "/finish") == {
        "number": 1,
        "taught_words": ["Höhle"],
        "topics": [],
    }
    with closing(VocabStore(tmp_path / "vocab.sqlite")) as store:
        assert store.state_of("Höhle") == WordState.TAUGHT
    assert get_json(base)["finished"] is True
    with pytest.raises(urllib.error.HTTPError) as again:
        post_json(base + "/finish")
    assert again.value.code == 400


def test_the_review_tab_gets_the_due_cards_and_grades_one(tmp_path, page, port):
    with closing(VocabStore(tmp_path / "vocab.sqlite")) as store:
        store.add("Höhle", "NOUN", WordState.UNKNOWN)
        store.keep_episode_line(
            "Höhle", EpisodeLine("Dark/S01E01", 1, "Sie sind in der Höhle.")
        )
        # Taught yesterday: the web server uses the computer's clock.
        yesterday = date.today() - timedelta(days=1)
        store.teach("Höhle", Teaching("Dark/S01E01", yesterday, "Höhle", "cave", "feminine"))
    page.open("Dark/S01E01")
    base = f"http://127.0.0.1:{port}/api/reviews"

    assert get_json(base) == [
        {
            "base_form": "Höhle",
            "word_type": "NOUN",
            "seen_form": "Höhle",
            "context": "Sie sind in der **Höhle**.",
            "first_review": True,
            "meaning": "cave",
            "needs_article": True,
        }
    ]
    graded = post_json(base, {"base_form": "Höhle", "rating": "Good", "article": "das"})
    assert graded["rating"] == "Good"
    assert graded["article"] == {
        "right": False,
        "correction": "die Höhle",
        "reason": "Höhle is feminine: die Höhle.",
    }
    assert get_json(base) == []  # Due again in 10 minutes.
    with pytest.raises(urllib.error.HTTPError) as rejected:
        post_json(base, {"base_form": "Höhle", "rating": "Good", "article": "die"})
    assert rejected.value.code == 400
