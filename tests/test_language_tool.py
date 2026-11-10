"""The LanguageTool adapter, with a fake transport instead of the network."""

import json
import urllib.error
from urllib.parse import parse_qs

import pytest

from core import Issue, LanguageToolBusy
from core.language_tool import PUBLIC_URL, LanguageTool, LanguageToolError

# A cut-down answer of the public server for "Ich habe ein Hauss."
ANSWER = {
    "matches": [
        {
            "message": "Möglicher Tippfehler gefunden.",
            "offset": 14,
            "length": 5,
            "replacements": [{"value": "Haus"}, {"value": "Hauses"}, {"value": "Hausse"}, {"value": "Hans"}],
            "context": {"text": "Ich habe ein Hauss.", "offset": 13, "length": 5},
            "rule": {"id": "GERMAN_SPELLER_RULE", "issueType": "misspelling"},
        },
        {
            "message": "Drei Sätze beginnen mit dem gleichen Wort.",
            "offset": 0,
            "length": 3,
            "replacements": [],
            "context": {"text": "Ich habe ein Hauss.", "offset": 0, "length": 3},
            "rule": {"id": "GERMAN_WORD_REPEAT_BEGINNING_RULE", "issueType": "style"},
        },
    ]
}


class FakeTransport:
    def __init__(self, answer=ANSWER, error=None):
        self.answer = answer
        self.error = error
        self.requests: list[tuple[str, dict]] = []

    def __call__(self, url: str, body: bytes) -> bytes:
        self.requests.append((url, parse_qs(body.decode("utf-8"))))
        if self.error:
            raise self.error
        return json.dumps(self.answer).encode("utf-8")


def test_a_text_is_sent_to_the_public_server_as_german():
    transport = FakeTransport()

    LanguageTool(post=transport).check(" Ich habe ein Hauss.")

    ((url, form),) = transport.requests
    assert url == PUBLIC_URL
    assert form["text"] == [" Ich habe ein Hauss."]
    assert form["language"] == ["de-DE"]


def test_each_match_becomes_an_issue_with_the_flagged_words_and_suggestions():
    issues = LanguageTool(post=FakeTransport()).check(" Ich habe ein Hauss.")

    assert issues == [
        Issue(14, 5, 'Möglicher Tippfehler gefunden. "Hauss" -> Haus, Hauses, Hausse', "misspelling"),
        Issue(0, 3, 'Drei Sätze beginnen mit dem gleichen Wort. "Ich"', "style"),
    ]


@pytest.mark.parametrize(
    "error, message",
    [
        (urllib.error.HTTPError(PUBLIC_URL, 500, "Server Error", {}, None), "500"),
        (urllib.error.URLError("no network"), "cannot be reached"),
        (TimeoutError("timed out"), "cannot be reached"),
    ],
)
def test_a_failed_request_is_a_languagetool_error(error, message):
    with pytest.raises(LanguageToolError, match=message):
        LanguageTool(post=FakeTransport(error=error)).check("Hallo.")


def test_an_answer_that_is_not_json_is_a_languagetool_error():
    def busy_server(url: str, body: bytes) -> bytes:
        return b"<html>busy</html>"

    with pytest.raises(LanguageToolError, match="not understood"):
        LanguageTool(post=busy_server).check("Hallo.")


def test_the_flagged_words_are_found_after_characters_outside_the_bmp():
    smiley = "\U0001F600"  # 2 UTF-16 code units, as LanguageTool counts
    answer = {
        "matches": [
            {
                "message": "Möglicher Tippfehler gefunden.",
                "offset": 4,
                "length": 5,
                "replacements": [],
                "context": {"text": f"{smiley} Ein Hauss.", "offset": 7, "length": 5},
                "rule": {"issueType": "misspelling"},
            }
        ]
    }

    (issue,) = LanguageTool(post=FakeTransport(answer)).check(f"{smiley} Ein Hauss.")

    assert issue.message == 'Möglicher Tippfehler gefunden. "Hauss"'


def test_too_many_requests_means_languagetool_is_busy():
    error = urllib.error.HTTPError(PUBLIC_URL, 429, "Too Many Requests", {}, None)

    with pytest.raises(LanguageToolBusy, match="rate limit"):
        LanguageTool(post=FakeTransport(error=error)).check("Hallo.")
