"""Example sentences: 3 sentences that teach each word a Lesson picks.

The words are Unknown words when their sentences are written, and Taught
words after their Lesson. An agent writes the sentences. LanguageTool checks each one before it is
stored. The retry policy lives here, not in the agent.
"""

from bisect import bisect_right
from collections import deque
from collections.abc import Collection, Iterator
from dataclasses import dataclass
from enum import Enum
from itertools import accumulate
from typing import Protocol
from urllib.parse import quote_plus

from core.vocab_store import VocabStore, WordState

SENTENCES_PER_WORD = 3
MAX_RETRIES = 3
MAX_SENTENCE_LENGTH = 300
_TEACHABLE = {WordState.UNKNOWN, WordState.TAUGHT}

_SEPARATOR = "\n\n"
_MINUTE = 60.0
_NOT_PROBLEMS = {"style"}


@dataclass(frozen=True)
class Issue:
    """One problem LanguageTool found in a text.

    The offset and length count UTF-16 code units, as LanguageTool does.
    """

    offset: int
    length: int
    message: str
    issue_type: str


class LanguageToolBusy(ValueError):
    """LanguageTool answered "too many requests"."""


class LanguageToolApi(Protocol):
    def check(self, text: str) -> list[Issue]:
        """Check a German text; give the problems found.

        Raises LanguageToolBusy when the server says "too many requests".
        """


class Clock(Protocol):
    def now(self) -> float:
        """Seconds, from any fixed point."""

    def sleep(self, seconds: float) -> None:
        """Wait."""


class SentenceChecker:
    """Checks sentences with LanguageTool, in batches, under its rate limits.

    The public LanguageTool server takes at most 20 requests, 75 KB per minute
    and 20 KB per request. So the sentences go in as few requests as fit, one
    paragraph per sentence, and a request waits when the last minute is full.
    Style hints (for example "three sentences start with the same word") are
    not problems: they are no errors, and in a batch they can come from other
    sentences.
    """

    def __init__(
        self,
        language_tool: LanguageToolApi,
        clock: Clock,
        max_requests_per_minute: int = 20,
        max_bytes_per_minute: int = 75_000,
        max_request_bytes: int = 18_000,
    ):
        self._language_tool = language_tool
        self._clock = clock
        self._max_requests = max_requests_per_minute
        self._max_bytes = max_bytes_per_minute
        self._max_request_bytes = max_request_bytes
        self._sent: deque[tuple[float, int]] = deque()

    def check(self, sentences: list[str]) -> list[list[str]]:
        """The problems of each sentence; an empty list for a sentence that passes."""
        problems: list[list[str]] = [[] for _ in sentences]
        for batch in self._batches(sentences):
            text = _SEPARATOR.join(sentences[index] for index in batch)
            # Where each sentence starts in the text, in LanguageTool's units.
            starts = list(
                accumulate(
                    (_utf16_length(sentences[index] + _SEPARATOR) for index in batch[:-1]),
                    initial=0,
                )
            )
            for issue in self._send(text):
                if issue.issue_type in _NOT_PROBLEMS:
                    continue
                position = max(bisect_right(starts, issue.offset) - 1, 0)
                problems[batch[position]].append(issue.message)
        return problems

    def _send(self, text: str) -> list[Issue]:
        """Send one request; when LanguageTool is busy, ask once more a minute later.

        The server can be busy when its limit is shared, for example with
        another program on the same computer.
        """
        try:
            return self._send_now(text)
        except LanguageToolBusy:
            self._clock.sleep(_MINUTE)
            return self._send_now(text)

    def _send_now(self, text: str) -> list[Issue]:
        self._wait_for(_size(text))
        self._sent.append((self._clock.now(), _size(text)))
        return self._language_tool.check(text)

    def _batches(self, sentences: list[str]) -> Iterator[list[int]]:
        batch: list[int] = []
        size = 0
        for index, sentence in enumerate(sentences):
            grown = size + _size(_SEPARATOR) + _size(sentence)
            if batch and grown > self._max_request_bytes:
                yield batch
                batch = []
            size = grown if batch else _size(sentence)
            batch.append(index)
        if batch:
            yield batch

    def _wait_for(self, size: int) -> None:
        while True:
            now = self._clock.now()
            while self._sent and self._sent[0][0] <= now - _MINUTE:
                self._sent.popleft()
            if not self._sent or (
                len(self._sent) < self._max_requests
                and sum(sent for _, sent in self._sent) + size <= self._max_bytes
            ):
                return
            self._clock.sleep(self._sent[0][0] + _MINUTE - now)


def _size(text: str) -> int:
    """The size of a text in a request body, where "ü" takes 6 bytes."""
    return len(quote_plus(text))


def _utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


@dataclass(frozen=True)
class SentenceToStore:
    """An example sentence an agent wrote: sentence 1, 2 or 3 of a Base form."""

    base_form: str
    number: int
    sentence: str


class SentenceStatus(str, Enum):
    STORED = "stored"
    RETRY = "retry"  # It failed; the agent writes a new sentence with the same number.
    LISTED = "listed"  # It failed its last retry; it is on the list for the learner.


@dataclass(frozen=True)
class SentenceResult:
    base_form: str
    number: int
    sentence: str
    status: SentenceStatus
    problems: list[str]
    retries_left: int | None  # None for a stored sentence


def add_sentences(
    store: VocabStore,
    checker: SentenceChecker,
    sentences: list[SentenceToStore],
    picked: Collection[str] | None = None,
) -> list[SentenceResult]:
    """Check example sentences with LanguageTool and store the ones that pass.

    A sentence that fails can be retried up to 3 times: the agent writes a new
    sentence with the same number. When the last retry fails too, the sentence
    goes on the list for the learner and takes no more tries.

    `picked` holds the Base forms a Lesson picked; a sentence for any other
    word is rejected. With None, any Unknown or Taught word takes sentences.
    """
    sentences = _checked_input(store, sentences, picked)
    results = []
    for item, problems in zip(sentences, checker.check([s.sentence for s in sentences])):
        if problems:
            failures = store.add_failed_try(
                item.base_form, item.number, item.sentence, problems
            )
            results.append(_result(item, problems, failures))
        else:
            store.add_example_sentence(item.base_form, item.number, item.sentence)
            results.append(
                SentenceResult(
                    item.base_form, item.number, item.sentence, SentenceStatus.STORED, [], None
                )
            )
    return results


def failed_sentences(
    store: VocabStore, picked: Collection[str] | None = None
) -> list[SentenceResult]:
    """The list for the learner: example sentences whose last try failed.

    A "listed" sentence failed all its retries. A "retry" sentence still has
    retries left, but the agent stopped before it sent a new one. With
    `picked`, only the sentences of these Base forms are listed.
    """
    return [
        _result(
            SentenceToStore(failed.base_form, failed.number, failed.sentence),
            failed.problems,
            failed.failures,
        )
        for failed in store.failed_sentences()
        if picked is None or failed.base_form in picked
    ]


def _result(item: SentenceToStore, problems: list[str], failures: int) -> SentenceResult:
    retries_left = max(MAX_RETRIES + 1 - failures, 0)
    status = SentenceStatus.RETRY if retries_left else SentenceStatus.LISTED
    return SentenceResult(
        item.base_form, item.number, item.sentence, status, problems, retries_left
    )


def _checked_input(
    store: VocabStore,
    sentences: list[SentenceToStore],
    picked: Collection[str] | None,
) -> list[SentenceToStore]:
    """The sentences with outer spaces removed; ValueError if any one is bad."""
    seen = set()
    cleaned = []
    for item in sentences:
        name = f"Sentence {item.number} of {item.base_form!r}"
        if picked is not None and item.base_form not in picked:
            raise ValueError(
                f"{item.base_form!r} is not a word the Lesson picked: write "
                "sentences only for the words pick_lesson_words gives"
            )
        if store.state_of(item.base_form) not in _TEACHABLE:
            raise ValueError(f"{item.base_form!r} is not an Unknown or Taught word")
        if item.number not in range(1, SENTENCES_PER_WORD + 1):
            raise ValueError(f"{name}: the number must be 1, 2 or 3")
        sentence = item.sentence.strip()
        if not sentence:
            raise ValueError(f"{name} is empty")
        if len(sentence) > MAX_SENTENCE_LENGTH:
            raise ValueError(
                f"{name} is too long; use at most {MAX_SENTENCE_LENGTH} characters"
            )
        if len(sentence.splitlines()) > 1:
            raise ValueError(f"{name} must be one line")
        if (item.base_form, item.number) in seen:
            raise ValueError(f"{name} is in this call twice")
        seen.add((item.base_form, item.number))
        if item.number in store.example_sentences(item.base_form):
            raise ValueError(f"{name} is already stored")
        if store.failed_tries(item.base_form, item.number) > MAX_RETRIES:
            raise ValueError(
                f"{name} is on the list for the learner; it takes no more tries"
            )
        cleaned.append(SentenceToStore(item.base_form, item.number, sentence))
    return cleaned
