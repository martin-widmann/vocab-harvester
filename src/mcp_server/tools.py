"""The MCP tools. Each tool only calls the core and turns its answer into JSON."""

from collections.abc import Callable
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from core import (
    Curriculum,
    Episode,
    Exercise,
    ExerciseStock,
    FoundTopic,
    FrequencyTable,
    GrammarPart,
    LessonExercise,
    LessonFiles,
    Line,
    OpenKind,
    SentenceChecker,
    SentenceToStore,
    Topic,
    TopicStatus,
    VocabStore,
    WordFacts,
    add_exercises,
    add_sentences,
    analyse,
    curriculum_gaps,
    episode_key,
    episode_lines,
    failed_sentences,
    find_episode,
    match_episode,
    new_words,
    pick_lesson_words,
    report_topics,
    tagged_subtitles_path,
    wait_for_check,
    write_lesson,
)
from core.frequency import DEFAULT_FREQUENCY
from core.language_tool import LanguageTool, SystemClock
from core.sentences import Clock, LanguageToolApi
from core.word_facts import DEFAULT_FACTS
from web.launch import PageError

_EPISODE = {
    "type": "string",
    "description": "The Episode name under the media folder, for example "
    '"Dark/S01E03", or for a film its Episode P1-P3, for example "Der Film/P2".',
}

_WORD = {
    "type": "object",
    "properties": {
        "base_form": {"type": "string"},
        "word_type": {"type": "string"},
    },
    "required": ["base_form", "word_type"],
    "additionalProperties": False,
}

_SENTENCE = {
    "type": "object",
    "properties": {
        "base_form": {"type": "string"},
        "number": {"type": "integer", "minimum": 1, "maximum": 3},
        "sentence": {"type": "string"},
    },
    "required": ["base_form", "number", "sentence"],
    "additionalProperties": False,
}

_TOPIC = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "level": {"type": "string"},
    },
    "required": ["id", "name", "level"],
    "additionalProperties": False,
}

_FOUND_TOPIC = {
    "type": "object",
    "properties": {
        "topic_id": {"type": "string"},
        "lines": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["topic_id", "lines"],
    "additionalProperties": False,
}

_EXERCISE = {
    "type": "object",
    "properties": {
        "topic_id": {"type": "string"},
        "kind": {"type": "string", "enum": ["gap", "choice"]},
        "sentence": {"type": "string"},
        "answer": {"type": "string"},
        "options": {"type": "array", "items": {"type": "string"}},
        "explanation": {"type": "string"},
    },
    "required": ["topic_id", "kind", "sentence", "answer", "options", "explanation"],
    "additionalProperties": False,
}

_LESSON_EXERCISE = {
    "type": "object",
    "properties": {
        "kind": {
            "type": "string",
            "enum": ["gap", "choice", *(kind.value for kind in OpenKind)],
        },
        "sentence": {"type": "string"},
        "answer": {"type": "string"},
        "options": {"type": "array", "items": {"type": "string"}},
        "explanation": {"type": "string"},
    },
    "required": ["kind", "sentence", "answer", "options", "explanation"],
    "additionalProperties": False,
}

_GRAMMAR_PART = {
    "type": "object",
    "properties": {
        "topic_id": {"type": "string"},
        "example": {"type": "string"},
        "line": {"type": ["integer", "null"]},
        "rule": {"type": "string"},
        "cases": {"type": "array", "items": {"type": "string"}},
        "exercises": {"type": "array", "items": _LESSON_EXERCISE},
    },
    "required": ["topic_id", "example", "line", "rule", "cases", "exercises"],
    "additionalProperties": False,
}

_JSON_TYPES = {
    "string": str, "integer": int, "array": list, "object": dict, "null": type(None)
}


class Page(Protocol):
    def open(self, episode: str) -> str:
        """Open the exercise page of an Episode; give its URL."""


class ToolError(Exception):
    """A tool call that cannot be done, for example an unknown Episode."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    properties: dict
    handler: Callable

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": self.properties,
            "required": list(self.properties),
            "additionalProperties": False,
        }

    def check(self, arguments: dict) -> None:
        missing = set(self.properties) - set(arguments)
        extra = set(arguments) - set(self.properties)
        if missing or extra:
            raise ToolError(
                f"{self.name} needs exactly {sorted(self.properties)}; "
                f"missing {sorted(missing)}, not known {sorted(extra)}"
            )
        for key, value in arguments.items():
            _check_value(key, value, self.properties[key])


def _check_value(name: str, value, schema: dict) -> None:
    """Check a value against the small part of JSON Schema the tools use."""
    types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
    if isinstance(value, bool) or not any(
        isinstance(value, _JSON_TYPES[json_type]) for json_type in types
    ):
        raise ToolError(f"{name} must be of type {' or '.join(types)}")
    if schema["type"] == "array":
        for item in value:
            _check_value(f"each item of {name}", item, schema["items"])
    if schema["type"] == "object":
        fields = schema["properties"]
        if set(value) != set(fields):
            raise ToolError(f"{name} must have exactly {sorted(fields)}")
        for key, field_value in value.items():
            _check_value(f"{key} in {name}", field_value, fields[key])


class Toolbox:
    """The tools the agents can call. Each one is a thin call into the core."""

    def __init__(
        self,
        media_root: Path | str,
        db_path: Path | str,
        page: Page,
        facts_path: Path | str = DEFAULT_FACTS,
        frequency_path: Path | str = DEFAULT_FREQUENCY,
        language_tool: LanguageToolApi | None = None,
        clock: Clock | None = None,
    ):
        self._media_root = Path(media_root)
        self._db_path = Path(db_path)
        self._facts_path = Path(facts_path)
        self._frequency_path = Path(frequency_path)
        self._page = page
        self._clock = clock or SystemClock()
        # One checker for the whole session, so the rate limit holds across calls.
        self._checker = SentenceChecker(language_tool or LanguageTool(), self._clock)
        self.tools = {
            tool.name: tool
            for tool in [
                Tool(
                    "find_episode",
                    "Find an Episode from how the learner names it, for example "
                    '"Dark S01E03", "dark s1e3" or "Der Film P2". The result '
                    'gives its Episode name in the media folder ("Dark/S01E03") '
                    "for all other tools, and the number of its Lesson, or null "
                    "if it has no Lesson yet. If there is no such Episode, the "
                    "error names the series, films or Episodes there are.",
                    {
                        "name": {
                            "type": "string",
                            "description": "The series or film name and the "
                            'Episode code, for example "Dark S01E03" or '
                            '"Der Film P2".',
                        }
                    },
                    self._find_episode,
                ),
                Tool(
                    "parse_subtitles",
                    "Read the .srt file of an Episode into Lines: number, "
                    "start and end in seconds, and text.",
                    {"episode": _EPISODE},
                    self._parse_subtitles,
                ),
                Tool(
                    "split_words",
                    "Reduce the text of one Line to its words: Base form, "
                    "word type and Seen form. Separable verbs are joined; "
                    "names, places and filler sounds are left out.",
                    {"text": {"type": "string", "description": "The text of a Line."}},
                    self._split_words,
                ),
                Tool(
                    "vocab_lookup",
                    "Give the word state (Known, Unknown, Taught, Excluded) of "
                    "each Base form, or null if it is not in the vocab store.",
                    {
                        "base_forms": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": 'Base forms, for example ["geben"].',
                        }
                    },
                    self._vocab_lookup,
                ),
                Tool(
                    "new_words",
                    "Process an Episode: list its New words (Base form and word "
                    "type), in the order they are first heard.",
                    {"episode": _EPISODE},
                    self._new_words,
                ),
                Tool(
                    "wait_for_check",
                    "Wait while the learner does the Word Knowledge Check of "
                    "an Episode on the Check tab. It returns when every New "
                    "word is marked (done is true), or after 5 minutes with "
                    "done false: then call it again. checked counts the words "
                    "marked during this wait, left the New words not marked yet.",
                    {"episode": _EPISODE},
                    self._wait_for_check,
                ),
                Tool(
                    "word_facts",
                    "Give the word facts of each word from the offline "
                    "Wiktionary data: meaning, gender, plural and verb forms "
                    "(present, past, participle, auxiliary). A noun compound "
                    "missing from the data is split into parts, with gender "
                    "and plural from its last part and no meaning. "
                    'meaning_status is "checked" for a meaning from the data '
                    'and "unchecked" for one an agent added.',
                    {
                        "words": {
                            "type": "array",
                            "items": _WORD,
                            "description": "Words as new_words gives them, for "
                            'example [{"base_form": "geben", "word_type": "VERB"}].',
                        }
                    },
                    self._word_facts,
                ),
                Tool(
                    "add_word_meaning",
                    "Store a short English meaning for a word that has no "
                    "meaning in the word facts data, for example a split "
                    'compound. It is marked "unchecked". A meaning from the '
                    "data cannot be replaced.",
                    {
                        "base_form": {"type": "string", "description": "The Base form."},
                        "meaning": {
                            "type": "string",
                            "description": 'A short English meaning, for example "homicide squad".',
                        },
                    },
                    self._add_word_meaning,
                ),
                Tool(
                    "pick_lesson_words",
                    "Pick the words the Lesson of an Episode teaches: up to 20 "
                    "Unknown words of the Episode, the most frequent first "
                    "(count from the subtitle frequency table; words not in the "
                    "table come last, with count null). Each word has the "
                    "Section (1, 2 or 3, for about 0-15, 15-30 and 30-45 "
                    "minutes) and the Line where it is first heard, and its "
                    "Seen form there. Use it after the Word Knowledge Check. "
                    "It changes no word state.",
                    {"episode": _EPISODE},
                    self._pick_lesson_words,
                ),
                Tool(
                    "add_sentences",
                    "Store example sentences for the words the Lesson of an "
                    "Episode picked (pick_lesson_words): sentence 1, 2 and 3 "
                    "of each Base form. A sentence for any other word is "
                    "rejected. LanguageTool checks "
                    "every sentence first; only a sentence with no problems is "
                    "stored. Send all sentences in one call. Each result has a "
                    'status: "stored"; "retry" (it failed: write a new sentence '
                    "with the same number, retries_left tells how many tries "
                    'are left); or "listed" (it failed its last retry and is on '
                    "the list for the learner; it takes no more tries). "
                    "problems gives what LanguageTool found.",
                    {
                        "episode": _EPISODE,
                        "sentences": {
                            "type": "array",
                            "items": _SENTENCE,
                            "description": 'For example [{"base_form": "aufgeben", '
                            '"number": 1, "sentence": "Er gibt nie auf."}].',
                        }
                    },
                    self._add_sentences,
                ),
                Tool(
                    "failed_sentences",
                    "Give the list for the learner: example sentences of the "
                    "words the Lesson of an Episode picked, whose last "
                    "LanguageTool check failed, with the problems found. "
                    'Status "listed": it failed all its retries. Status '
                    '"retry": it has retries left, but no new sentence was sent. '
                    "None of them is stored.",
                    {"episode": _EPISODE},
                    self._failed_sentences,
                ),
                Tool(
                    "curriculum",
                    "Give the Curriculum: each Grammar topic in order, with its "
                    "Topic state (Not seen, Seen, Learned, Solid) and whether it "
                    "is a Weak point. Also give the open proposal that waits for "
                    "the learner's approval, or null.",
                    {},
                    self._curriculum,
                ),
                Tool(
                    "propose_curriculum",
                    "Propose a full Curriculum: the first draft or a change. It "
                    "is NOT stored as the Curriculum; it waits until the learner "
                    "approves it on the command line with "
                    "`python -m core approve-curriculum <number>`. It replaces "
                    "an older open proposal. Send every "
                    "topic, in teaching order, with an id (lowercase, hyphens, "
                    'for example "konjunktiv-2"), the name a Tag shows (for '
                    'example "Konjunktiv II") and its level (A1, A2, B1, B2, C1 '
                    "or C2). On approval, a kept topic keeps its Topic state; an "
                    "added topic starts as Solid up to B1, else as Not seen; a "
                    "removed topic loses its Topic state. The result gives the "
                    "proposal number and the ids it adds and removes.",
                    {
                        "topics": {
                            "type": "array",
                            "items": _TOPIC,
                            "description": 'For example [{"id": "dativ", '
                            '"name": "Dativ", "level": "A2"}].',
                        }
                    },
                    self._propose_curriculum,
                ),
                Tool(
                    "curriculum_gaps",
                    "Pick the 2 Grammar topics a Lesson teaches, from the topics "
                    "found in its Episode: new is the first Not seen topic in "
                    "Curriculum order, weak is the Weak point that has been weak "
                    "the longest. Either is null when the Episode has none. "
                    "not_in_curriculum names found topic ids the Curriculum does "
                    "not have (propose a change if they belong in it).",
                    {
                        "found_topics": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Ids of the Curriculum topics found in "
                            "the Episode's Lines, for example "
                            '["dativ", "konjunktiv-1"].',
                        }
                    },
                    self._curriculum_gaps,
                ),
                Tool(
                    "report_topics",
                    "Start the grammar part of a lesson build: report the "
                    "Grammar topics found in an Episode's Lines, each with the "
                    "numbers of the Lines it occurs in. A new report for the "
                    "Episode replaces the old one. The result gives the 2 "
                    "topics the Lesson teaches, each with its Lines: new (the "
                    "first Not seen topic in Curriculum order) and weak (the "
                    "Weak point that has been weak the longest); either is "
                    "null when the Episode has none. not_in_curriculum names "
                    "found topic ids the Curriculum does not have. refill "
                    "names the topics whose exercise stock needs exercises "
                    "now (the picked ones and every topic whose stock is low) "
                    "and how many each needs; only these topics take "
                    "exercises until the next lesson build.",
                    {
                        "episode": _EPISODE,
                        "topics": {
                            "type": "array",
                            "items": _FOUND_TOPIC,
                            "description": 'For example [{"topic_id": "dativ", '
                            '"lines": [12, 40]}]. Use the Curriculum topic ids.',
                        },
                    },
                    self._report_topics,
                ),
                Tool(
                    "add_exercises",
                    "Store grammar exercises in the exercise stock, for the "
                    "topics in the refill of the latest report_topics call, "
                    "up to 5 unused exercises per topic. An exercise is one "
                    'German sentence with one gap "___", the answer for the '
                    'gap, and a short English explanation. kind "gap": the '
                    'learner types the answer, options is []. kind "choice": '
                    "2 to 4 options, the answer one of them. LanguageTool "
                    "checks each sentence with the answer in the gap; only an "
                    "exercise with no problems is stored. Each result has a "
                    'status: "stored"; "retry" (it failed: write a new '
                    "exercise for the topic; retries_left is the failed tries "
                    'the topic has left in this lesson build); or "stopped" '
                    "(the topic failed all its tries: send no more exercises "
                    "for it until the next lesson build).",
                    {
                        "exercises": {
                            "type": "array",
                            "items": _EXERCISE,
                            "description": 'For example [{"topic_id": "dativ", '
                            '"kind": "choice", "sentence": "Ich helfe ___ Mann.", '
                            '"answer": "dem", "options": ["dem", "den", "der"], '
                            '"explanation": "helfen takes the dative."}].',
                        }
                    },
                    self._add_exercises,
                ),
                Tool(
                    "write_lesson",
                    "Write the Lesson file of an Episode, after pick_lesson_words, "
                    "add_sentences and report_topics. Send only the grammar part: "
                    "one item for each of the 2 Grammar topics report_topics "
                    "picked (new and weak). The core adds the picked words, each "
                    "in the Section where it is first heard, with its word facts "
                    "and stored example sentences, and puts each Grammar topic in "
                    "the Section of its Line. Per topic: example, the first "
                    "sentence the learner sees; line, null for a neutral example, "
                    "or the number of the episode Line the example comes from (one "
                    "of the topic's Lines from report_topics; then cut the Line to "
                    "the part with the topic and change every name); rule, the "
                    "full rule in English; cases, 2 to 6 more German example "
                    "sentences of the rule; exercises, 2 to 4 Lesson exercises "
                    "of the rule, in the same shape as add_exercises but without "
                    "topic_id (the learner sees no answer or explanation until "
                    "they answer). A Lesson exercise may also be open, checked by "
                    'the grader: kind "sentence" (sentence is the task, for '
                    'example "Write your own sentence with helfen."; answer one '
                    'correct German sentence), "translate" (sentence is an '
                    "English sentence; answer its German translation) or "
                    '"explain" (sentence is a German sentence and a why '
                    "question; answer the reason in one short English sentence). "
                    "An open exercise has no gap and options is []. The core adds a der/die/das exercise for each "
                    "noun with a gender. No text may use a name of a person or "
                    "place from the Episode or copy a whole Line. LanguageTool "
                    "checks the example, the cases, each exercise with its "
                    "answer in the gap, and the German answer of each sentence "
                    "and translate exercise. A Lesson that already has answers cannot "
                    "be replaced. A Lesson that breaks a "
                    "rule is rejected and nothing is written: fix it and call "
                    "again. A new call for the same Episode replaces its Lesson. "
                    "The core also writes the tagged German subtitles next to the "
                    "video: the Base form of each Taught word on the first 2 Lines "
                    "it is heard in, and the name of each Grammar topic on the Line "
                    "of its example and on its first 2 Lines from report_topics. "
                    "The result gives the Lesson number, per Section its "
                    "words and topics, and the name of the tagged subtitle file.",
                    {
                        "episode": _EPISODE,
                        "grammar": {
                            "type": "array",
                            "items": _GRAMMAR_PART,
                            "description": 'For example [{"topic_id": "dativ", '
                            '"example": "Ich helfe dem Mann.", "line": null, '
                            '"rule": "helfen, danken and folgen take a dative '
                            'object.", "cases": ["Wir danken dir.", '
                            '"Sie folgt dem Weg."], "exercises": [{"kind": '
                            '"choice", "sentence": "Wir danken ___ Frau.", '
                            '"answer": "der", "options": ["der", "die", "den"], '
                            '"explanation": "danken takes the dative."}, '
                            '{"kind": "gap", "sentence": "Ich folge ___ Weg.", '
                            '"answer": "dem", "options": [], "explanation": '
                            '"folgen takes the dative."}]}].',
                        },
                    },
                    self._write_lesson,
                ),
                Tool(
                    "open_page",
                    "Start the web server if it is not running and open the "
                    "exercise page of an Episode in the browser, on its Check tab.",
                    {"episode": _EPISODE},
                    self._open_page,
                ),
            ]
        }

    def call(self, name: str, arguments: dict):
        tool = self.tools.get(name)
        if tool is None:
            raise ToolError(f"Unknown tool {name!r}")
        tool.check(arguments)
        try:
            return tool.handler(**arguments)
        except (ValueError, PageError) as error:
            raise ToolError(str(error)) from error

    def _episode(self, name: str) -> Episode:
        return find_episode(self._media_root, name)

    def _find_episode(self, name: str) -> dict:
        key = match_episode(self._media_root, name)
        self._episode(key)
        lesson = LessonFiles.next_to(self._db_path).of_episode(key)
        return {"episode": key, "lesson": lesson and lesson["number"]}

    def _parse_subtitles(self, episode: str) -> list[dict]:
        return [
            _line(line) for line in episode_lines(self._episode(episode))
        ]

    def _split_words(self, text: str) -> list[dict]:
        return [asdict(word) for word in analyse(text)]

    def _vocab_lookup(self, base_forms: list[str]) -> dict:
        with closing(VocabStore(self._db_path)) as store:
            states = {form: store.state_of(form) for form in base_forms}
        return {form: state and state.value for form, state in states.items()}

    def _new_words(self, episode: str) -> list[dict]:
        with closing(VocabStore(self._db_path)) as store:
            return [asdict(word) for word in new_words(self._episode(episode), store)]

    def _wait_for_check(self, episode: str) -> dict:
        folder = self._episode(episode)
        with closing(VocabStore(self._db_path)) as store:
            return asdict(wait_for_check(folder, store, self._clock))

    def _word_facts(self, words: list[dict]) -> list[dict]:
        with closing(WordFacts(self._facts_path)) as facts:
            return [
                asdict(facts.lookup(word["base_form"], word["word_type"]))
                for word in words
            ]

    def _add_word_meaning(self, base_form: str, meaning: str) -> dict:
        with closing(WordFacts(self._facts_path)) as facts:
            facts.add_meaning(base_form, meaning)
            return asdict(facts.lookup(base_form))

    def _picked(self, episode: str) -> set[str]:
        """The Base forms the Lesson of an Episode picks."""
        return {word.base_form for word in self._lesson_words(episode)}

    def _lesson_words(self, episode: str) -> list:
        folder = self._episode(episode)
        with (
            closing(FrequencyTable(self._frequency_path)) as frequency,
            closing(VocabStore(self._db_path)) as store,
        ):
            return pick_lesson_words(folder, store, frequency)

    def _pick_lesson_words(self, episode: str) -> list[dict]:
        words = self._lesson_words(episode)
        return [
            {
                "base_form": word.base_form,
                "word_type": word.word_type,
                "count": word.count,
                "section": word.section,
                "seen_form": word.seen_form,
                "line": _line(word.line),
            }
            for word in words
        ]

    def _add_sentences(self, episode: str, sentences: list[dict]) -> list[dict]:
        picked = self._picked(episode)
        with closing(VocabStore(self._db_path)) as store:
            results = add_sentences(
                store,
                self._checker,
                [SentenceToStore(**sentence) for sentence in sentences],
                picked=picked,
            )
        return [asdict(result) for result in results]

    def _failed_sentences(self, episode: str) -> list[dict]:
        picked = self._picked(episode)
        with closing(VocabStore(self._db_path)) as store:
            return [asdict(failed) for failed in failed_sentences(store, picked)]

    def _curriculum(self) -> dict:
        with closing(Curriculum(self._db_path)) as curriculum:
            proposal = curriculum.proposal()
            return {
                "topics": [_topic_status(status) for status in curriculum.topics()],
                "proposal": proposal and asdict(proposal),
            }

    def _propose_curriculum(self, topics: list[dict]) -> dict:
        with closing(Curriculum(self._db_path)) as curriculum:
            return asdict(curriculum.propose([Topic(**topic) for topic in topics]))

    def _curriculum_gaps(self, found_topics: list[str]) -> dict:
        with closing(Curriculum(self._db_path)) as curriculum:
            return asdict(curriculum_gaps(curriculum, found_topics))

    def _report_topics(self, episode: str, topics: list[dict]) -> dict:
        key = episode_key(self._media_root, episode)
        lines = episode_lines(self._episode(episode))
        with (
            closing(Curriculum(self._db_path)) as curriculum,
            closing(ExerciseStock(self._db_path)) as stock,
        ):
            grammar = report_topics(
                curriculum, stock, key, lines, [FoundTopic(**topic) for topic in topics]
            )
        return asdict(grammar)

    def _add_exercises(self, exercises: list[dict]) -> list[dict]:
        with (
            closing(Curriculum(self._db_path)) as curriculum,
            closing(ExerciseStock(self._db_path)) as stock,
        ):
            results = add_exercises(
                curriculum,
                stock,
                self._checker,
                [Exercise(**exercise) for exercise in exercises],
            )
        return [asdict(result) for result in results]

    def _write_lesson(self, episode: str, grammar: list[dict]) -> dict:
        key = episode_key(self._media_root, episode)
        with (
            closing(VocabStore(self._db_path)) as store,
            closing(FrequencyTable(self._frequency_path)) as frequency,
            closing(WordFacts(self._facts_path)) as facts,
            closing(Curriculum(self._db_path)) as curriculum,
            closing(ExerciseStock(self._db_path)) as stock,
        ):
            lesson = write_lesson(
                LessonFiles.next_to(self._db_path),
                key,
                self._episode(episode),
                store=store,
                frequency=frequency,
                facts=facts,
                curriculum=curriculum,
                stock=stock,
                checker=self._checker,
                grammar=[
                    GrammarPart(
                        **{
                            **part,
                            "exercises": [
                                LessonExercise(**exercise)
                                for exercise in part["exercises"]
                            ],
                        }
                    )
                    for part in grammar
                ],
            )
        return {
            "number": lesson["number"],
            "episode": lesson["episode"],
            "sections": [
                {
                    "number": section["number"],
                    "words": [word["base_form"] for word in section["words"]],
                    "grammar": [topic["topic_id"] for topic in section["grammar"]],
                }
                for section in lesson["sections"]
            ],
            "tagged_subtitles": tagged_subtitles_path(self._episode(episode)).name,
        }

    def _open_page(self, episode: str) -> dict:
        return {"url": self._page.open(episode)}


def _line(line: Line) -> dict:
    return {
        "number": line.number,
        "start": line.start.total_seconds(),
        "end": line.end.total_seconds(),
        "text": line.text,
    }


def _topic_status(status: TopicStatus) -> dict:
    return {**asdict(status.topic), "state": status.state.value, "weak": status.weak}
