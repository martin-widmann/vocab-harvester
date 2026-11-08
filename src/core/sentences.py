"""Example sentences: the sentences that teach a Taught word.

An agent writes the sentences. LanguageTool checks each one before it is
stored. The retry policy lives here, not in the agent.
"""

from bisect import bisect_right
from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import accumulate
from typing import Protocol

from core.vocab_store import FailedSentence, VocabStore, WordState

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


class LanguageToolApi(Protocol):
    def check(self, text: str) -> list[Issue]:
        """Check a German text; give the problems found."""


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
            self._wait_for(_size(text))
            self._sent.append((self._clock.now(), _size(text)))
            starts = list(accumulate(
                (_utf16_length(sentences[index]) + _utf16_length(_SEPARATOR) for index in batch[:-1]),
                initial=0,
            ))
            for issue in self._language_tool.check(text):
                if issue.issue_type in _NOT_PROBLEMS:
                    continue
                position = max(bisect_right(starts, issue.offset) - 1, 0)
                problems[batch[position]].append(issue.message)
        return problems

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
    return len(text.encode("utf-8"))


def _utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


@dataclass(frozen=True)
class SentenceToStore:
    """An example sentence an agent wrote: sentence 1, 2 or 3 of a Base form."""

    base_form: str
    number: int
    sentence: str


@dataclass(frozen=True)
class SentenceResult:
    base_form: str
    number: int
    sentence: str
    status: str
    problems: list[str]
    retries_left: int


def add_sentences(
    store: VocabStore, checker: SentenceChecker, sentences: list[SentenceToStore]
) -> list[SentenceResult]:
    """Check example sentences with LanguageTool and store the ones that pass.

    A sentence that fails can be retried up to 3 times: the agent writes a new
    sentence with the same number. When the last retry fails too, the sentence
    goes on the list for the learner and takes no more tries.
    """
    sentences = _checked_input(store, sentences)
    results = []
    for item, problems in zip(sentences, checker.check([s.sentence for s in sentences])):
        if not problems:
            store.add_example_sentence(item.base_form, item.number, item.sentence)
            status, retries_left = "stored", 0
        else:
            failures = store.add_failed_try(item.base_form, item.number)
            retries_left = MAX_RETRIES + 1 - failures
            status = "retry"
            if retries_left == 0:
                status = "listed"
                store.add_failed_sentence(
                    FailedSentence(item.base_form, item.number, item.sentence, problems)
                )
        results.append(
            SentenceResult(
                item.base_form, item.number, item.sentence, status, problems, retries_left
            )
        )
    return results


def _checked_input(
    store: VocabStore, sentences: list[SentenceToStore]
) -> list[SentenceToStore]:
    """The sentences with outer spaces removed; ValueError if any one is bad."""
    seen = set()
    cleaned = []
    for item in sentences:
        name = f"Sentence {item.number} of {item.base_form!r}"
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
        if (item.base_form, item.number) in seen:
            raise ValueError(f"{name} is in this call twice")
        seen.add((item.base_form, item.number))
        if item.number in store.example_sentences(item.base_form):
            raise ValueError(f"{name} is already stored")
        if store.is_failed_sentence(item.base_form, item.number):
            raise ValueError(
                f"{name} is on the list for the learner; it takes no more tries"
            )
        cleaned.append(SentenceToStore(item.base_form, item.number, sentence))
    return cleaned
