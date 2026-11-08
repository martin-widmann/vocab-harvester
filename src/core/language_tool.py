"""The LanguageTool adapter: checks German text on the public LanguageTool server.

Only the HTTP call lives here. Batching and the rate limit are in
core.sentences, so a local server can replace the public one later.
"""

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from urllib.parse import urlencode

from core.sentences import Issue

PUBLIC_URL = "https://api.languagetool.org/v2/check"
LANGUAGE = "de-DE"
_TIMEOUT = 30
_MAX_SUGGESTIONS = 3


class LanguageToolError(ValueError):
    """LanguageTool could not check a text."""


def _post(url: str, body: bytes) -> bytes:
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "german-media-learning/0.1",
        },
    )
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as answer:
        return answer.read()


class LanguageTool:
    """A LanguageTool server. `post` sends a form body to a URL and gives the answer."""

    def __init__(
        self, url: str = PUBLIC_URL, post: Callable[[str, bytes], bytes] = _post
    ):
        self._url = url
        self._post = post

    def check(self, text: str) -> list[Issue]:
        body = urlencode({"text": text, "language": LANGUAGE}).encode("utf-8")
        try:
            raw = self._post(self._url, body)
        except urllib.error.HTTPError as error:
            if error.code == 429:
                raise LanguageToolError(
                    "The LanguageTool rate limit is reached; try again in a minute"
                ) from error
            raise LanguageToolError(
                f"LanguageTool gave HTTP error {error.code}: {error.reason}"
            ) from error
        except (urllib.error.URLError, OSError) as error:
            raise LanguageToolError(f"LanguageTool cannot be reached: {error}") from error
        try:
            matches = json.loads(raw)["matches"]
            return [_issue(match) for match in matches]
        except (ValueError, KeyError, TypeError) as error:
            raise LanguageToolError(
                f"The answer of LanguageTool is not understood: {error}"
            ) from error


def _issue(match: dict) -> Issue:
    context = match["context"]
    flagged = context["text"][context["offset"] : context["offset"] + context["length"]]
    message = f'{match["message"]} "{flagged}"'
    suggestions = [r["value"] for r in match.get("replacements", [])][:_MAX_SUGGESTIONS]
    if suggestions:
        message += " -> " + ", ".join(suggestions)
    issue_type = match.get("rule", {}).get("issueType", "uncategorized")
    return Issue(match["offset"], match["length"], message, issue_type)


class SystemClock:
    """The real clock, for the rate limit."""

    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)
