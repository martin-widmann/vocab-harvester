"""Fakes for the adapters at the edges: LanguageTool, the clock and the grader runner."""

from core import Issue


class FakeLanguageTool:
    """Flags every sentence that contains a word from its list of bad words."""

    def __init__(self, bad_words=("falsch",), style_words=()):
        self.bad_words = bad_words
        self.style_words = style_words
        self.texts: list[str] = []

    def check(self, text: str) -> list[Issue]:
        self.texts.append(text)
        issues = []
        for words, issue_type in ((self.bad_words, "grammar"), (self.style_words, "style")):
            for word in words:
                start = text.find(word)
                while start != -1:
                    offset = len(text[:start].encode("utf-16-le")) // 2
                    issues.append(Issue(offset, len(word), f"Fehler: {word}", issue_type))
                    start = text.find(word, start + 1)
        return issues


class FakeClock:
    def __init__(self):
        self.time = 0.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.time

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.time += seconds


class FakeGraderRunner:
    """Answers each grader request with the next reply; keeps the requests."""

    def __init__(self, *replies: str):
        self.replies = list(replies)
        self.prompts: list[str] = []

    def run(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.replies.pop(0)
