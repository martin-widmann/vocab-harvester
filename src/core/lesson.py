"""The Lesson file: what a Lesson teaches, in story order, for the Lesson tab.

The agent writes only the judgment part: for each Grammar topic of the
Lesson an example, the full rule and more cases. The core adds the rest from
the data: the picked words with their Section, word facts and the stored
example sentences. A write that breaks a rule is rejected, and nothing is
written.
"""

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from core.curriculum import Curriculum
from core.frequency import FrequencyTable
from core.grammar_topics import GAP, Exercise, ExerciseStock, check_exercise
from core.lesson_words import SECTION_COUNT, SECTION_LENGTH, LessonWord, pick_lesson_words, section_of
from core.sentences import MAX_RETRIES, SENTENCES_PER_WORD, SentenceChecker
from core.subtitles import Line, read_lines
from core.episode import subtitle_file
from core.vocab_store import VocabStore
from core.word_analysis import names
from core.word_facts import WordFacts

SCHEMA_VERSION = 1
MAX_SENTENCE_LENGTH = 300
MAX_RULE_LENGTH = 2000
MIN_CASES = 2
MAX_CASES = 6
MIN_EXERCISES = 2
MAX_EXERCISES = 4
ARTICLE_KIND = "article"
ARTICLES = {"masculine": "der", "feminine": "die", "neuter": "das"}

_FILE_NAME = re.compile(r"lesson-(\d+)\.json")
_MARKUP = re.compile(r"<[^>]*>|\{[^}]*\}")
_WORD = re.compile(r"\w+")


@dataclass(frozen=True)
class LessonExercise:
    """A Lesson exercise of a Grammar topic: a sentence with one gap "___".

    kind "gap": the learner types the answer; "choice": 2 to 4 options, the
    answer one of them. The explanation is the short reason a result shows.
    """

    kind: str
    sentence: str
    answer: str
    options: list[str]
    explanation: str


@dataclass(frozen=True)
class GrammarPart:
    """What the agent writes for one Grammar topic of a Lesson.

    `example` comes first in the Lesson. It is a neutral sentence (`line` is
    None) or an episode Line cut to the topic part with its names changed
    (`line` is the number of that Line). `rule` teaches the full rule and
    `cases` are more example sentences of it. `exercises` are the 2 to 4
    Lesson exercises of the topic.
    """

    topic_id: str
    example: str
    line: int | None
    rule: str
    cases: list[str]
    exercises: list[LessonExercise] = field(default_factory=list)


@dataclass(frozen=True)
class LessonInfo:
    """One Lesson in the list of Lessons."""

    number: int
    episode: str


class LessonFiles:
    """The Lesson files, one JSON file per Lesson: lesson-001.json, ..."""

    def __init__(self, folder: Path | str):
        self._folder = Path(folder)

    @classmethod
    def next_to(cls, db_path: Path | str) -> "LessonFiles":
        """The Lesson files of a learner: the "lessons" folder next to the vocab file."""
        return cls(Path(db_path).parent / "lessons")

    def lessons(self) -> list[LessonInfo]:
        """Every Lesson, the newest first. A file that cannot be read is left out."""
        found = []
        for number, path in self._files():
            try:
                lesson = _load(path)
            except ValueError:
                continue
            found.append(LessonInfo(number, lesson["episode"]))
        return sorted(found, key=lambda info: -info.number)

    def read(self, number: int) -> dict:
        """The Lesson file with this number."""
        for found, path in self._files():
            if found == number:
                return _load(path)
        raise ValueError(f"There is no Lesson {number}")

    def of_episode(self, episode: str) -> dict | None:
        """The Lesson file of an Episode, or None if it has none."""
        for info in self.lessons():
            if info.episode == episode:
                return self.read(info.number)
        return None

    def number_for(self, episode: str) -> int:
        """The number of the Episode's Lesson; a new number if it has none yet.

        A new number comes after every Lesson file, also one that cannot be
        read, so a new Lesson never replaces it.
        """
        for info in self.lessons():
            if info.episode == episode:
                return info.number
        return max((number for number, _ in self._files()), default=0) + 1

    def results(self, number: int) -> dict:
        """The results file of a Lesson: the learner's answers and their results.

        {"answers": {exercise id: {"answer", "right", "correction", "reason"}},
        "finished": ...}; a Lesson with no answers yet has empty results.
        """
        lesson = self.read(number)
        path = self._results_path(number)
        if not path.exists():
            return {
                "schema_version": SCHEMA_VERSION,
                "lesson": number,
                "episode": lesson["episode"],
                "answers": {},
                "finished": False,
            }
        try:
            results = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"The results file {path.name} cannot be read: {error}")
        if (
            not isinstance(results, dict)
            or results.get("schema_version") != SCHEMA_VERSION
            or not isinstance(results.get("answers"), dict)
            or not isinstance(results.get("finished"), bool)
        ):
            raise ValueError(f"The results file {path.name} does not match the schema")
        return results

    def _write(self, lesson: dict) -> None:
        self._write_json(self._folder / f"lesson-{lesson['number']:03}.json", lesson)

    def _write_results(self, results: dict) -> None:
        self._write_json(self._results_path(results["lesson"]), results)

    def _results_path(self, number: int) -> Path:
        return self._folder / f"lesson-{number:03}.results.json"

    def _write_json(self, path: Path, content: dict) -> None:
        self._folder.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(
            json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(temporary, path)

    def _files(self) -> list[tuple[int, Path]]:
        if not self._folder.is_dir():
            return []
        files = []
        for path in self._folder.iterdir():
            match = _FILE_NAME.fullmatch(path.name)
            if match and path.is_file():
                files.append((int(match.group(1)), path))
        return files


def _load(path: Path) -> dict:
    try:
        lesson = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"The Lesson file {path.name} cannot be read: {error}")
    if (
        not isinstance(lesson, dict)
        or lesson.get("schema_version") != SCHEMA_VERSION
        or not isinstance(lesson.get("episode"), str)
        or not isinstance(lesson.get("sections"), list)
    ):
        raise ValueError(f"The Lesson file {path.name} does not match the schema")
    return lesson


def write_lesson(
    lessons: LessonFiles,
    episode: str,
    episode_folder: Path | str,
    *,
    store: VocabStore,
    frequency: FrequencyTable,
    facts: WordFacts,
    curriculum: Curriculum,
    stock: ExerciseStock,
    checker: SentenceChecker,
    grammar: list[GrammarPart],
) -> dict:
    """Write the Lesson file of an Episode; give its content.

    The words are the ones pick_lesson_words picks, each in the Section where
    it is first heard, with its word facts and stored example sentences, never
    with its episode Line. The Grammar topics are the 2 that report_topics
    picked for the Episode. A new write for the same Episode replaces its
    Lesson but keeps its number and its words: once the Lesson is done, its
    words are Taught words and no longer picked.
    """
    lines = read_lines(subtitle_file(episode_folder))
    topics = _checked_grammar(episode, lines, stock, curriculum, facts, grammar)
    previous = lessons.of_episode(episode)
    words = []
    if previous is None:
        words = pick_lesson_words(episode_folder, store, frequency)
        _check_sentences_stored(store, words)
    _check_with_language_tool(checker, topics)

    minutes = int(SECTION_LENGTH.total_seconds() // 60)
    sections: list[dict] = [
        {
            "number": number,
            # About how far into the Episode; the last Section runs to its end.
            "start_minute": (number - 1) * minutes,
            "end_minute": number * minutes if number < SECTION_COUNT else None,
            "words": [],
            "grammar": [],
        }
        for number in range(1, SECTION_COUNT + 1)
    ]
    for word in sorted(words, key=lambda word: word.line.number):
        sections[word.section - 1]["words"].append(_word(word, store, facts))
    if previous is not None:
        for section, old in zip(sections, previous["sections"]):
            section["words"] = old["words"]
    by_number = {line.number: line for line in lines}
    for topic in sorted(topics, key=_taught_at):
        sections[section_of(by_number[_taught_at(topic)]) - 1]["grammar"].append(topic)
    lesson = {
        "schema_version": SCHEMA_VERSION,
        "number": lessons.number_for(episode),
        "episode": episode,
        "sections": sections,
    }
    lessons._write(lesson)
    return lesson


def _taught_at(topic: dict) -> int:
    """The Line a Grammar topic is taught at: its example's, else the first it is in."""
    return topic["lines"][0] if topic["line"] is None else topic["line"]


def _checked_grammar(
    episode: str,
    lines: list[Line],
    stock: ExerciseStock,
    curriculum: Curriculum,
    facts: WordFacts,
    grammar: list[GrammarPart],
) -> list[dict]:
    """The Grammar topics of the Lesson file; ValueError if a part breaks a rule."""
    picks = stock.picked_topics(episode)
    if picks is None:
        raise ValueError(
            f"No Grammar topics are reported for {episode}: "
            "call report_topics for it first"
        )
    kinds = {topic_id: kind for kind, topic_id in picks.items() if topic_id}
    names_of = {status.topic.id: status.topic.name for status in curriculum.topics()}
    lines_of = {found.topic_id: found.lines for found in stock.found_topics(episode)}
    by_number = {line.number: line for line in lines}
    for topic_id in kinds:
        if topic_id not in names_of:
            raise ValueError(
                f"Grammar topic {topic_id!r} is not in the Curriculum any more: "
                f"call report_topics for {episode} again"
            )
        for number in lines_of.get(topic_id, []):
            if number not in by_number:
                raise ValueError(
                    f"The Episode has no Line {number} any more: "
                    f"call report_topics for {episode} again"
                )
    episode_names = {
        found
        for found in names(line.text for line in lines)
        if not _is_common_noun(facts, found)
    }
    episode_texts = {_plain(text) for line in lines for text in _texts_of(line)}
    seen: set[str] = set()
    topics = []
    for part in grammar:
        name = f"Grammar topic {part.topic_id!r}"
        if part.topic_id not in kinds:
            raise ValueError(
                f"{name} is not a Grammar topic this Lesson teaches; "
                f"it teaches {sorted(kinds) or 'none'}"
            )
        if part.topic_id in seen:
            raise ValueError(f"{name} is in the Lesson twice")
        seen.add(part.topic_id)
        part = _cleaned(part)
        _check_texts(name, part)
        if part.line is not None:
            if part.line not in lines_of[part.topic_id]:
                raise ValueError(
                    f"{name}: Line {part.line} is not a Line where the topic was "
                    f"found; use one of {lines_of[part.topic_id]}, or null for a "
                    "neutral example"
                )
            line_words = _WORD.findall(_clean(by_number[part.line].text))
            if len(_WORD.findall(part.example)) >= len(line_words):
                raise ValueError(
                    f"{name}: the example from Line {part.line} is not cut; cut it "
                    "to the part with the topic, or use a neutral example"
                )
        exercise_texts = [
            text
            for exercise in part.exercises
            for text in [_solved(exercise), *exercise.options, exercise.explanation]
        ]
        for text in [part.example, part.rule, *part.cases, *exercise_texts]:
            used = sorted(found for found in episode_names if _has_word(text, found))
            if used:
                raise ValueError(
                    f"{name}: {text!r} uses names from the Episode "
                    f"({', '.join(used)}); change them so the Lesson does not "
                    "spoil the plot"
                )
        solved_texts = [_solved(exercise) for exercise in part.exercises]
        for text in [part.example, *part.cases, *solved_texts]:
            if _plain(text) in episode_texts:
                raise ValueError(
                    f"{name}: {text!r} is a Line of the Episode; use a neutral "
                    "sentence, or set line and cut the Line to the topic part"
                )
        topics.append(
            {
                "topic_id": part.topic_id,
                "name": names_of[part.topic_id],
                "kind": kinds[part.topic_id],
                "example": part.example,
                "line": part.line,
                "lines": lines_of[part.topic_id],
                "rule": part.rule,
                "cases": part.cases,
                "exercises": [
                    {"id": f"{part.topic_id}:{n}", **asdict(exercise)}
                    for n, exercise in enumerate(part.exercises, 1)
                ],
            }
        )
    for topic_id in kinds:
        if topic_id not in seen:
            raise ValueError(f"The Lesson needs the Grammar topic {topic_id!r}")
    return topics


def _is_common_noun(facts: WordFacts, word: str) -> bool:
    """A noun of the word facts data that spaCy took for a name, as "Hund"."""
    found = facts.lookup(word, "NOUN")
    return found.meaning_status == "checked" and found.gender is not None


def _cleaned(part: GrammarPart) -> GrammarPart:
    return GrammarPart(
        part.topic_id,
        part.example.strip(),
        part.line,
        part.rule.strip(),
        [case.strip() for case in part.cases],
        [
            LessonExercise(
                exercise.kind,
                exercise.sentence.strip(),
                exercise.answer.strip(),
                [option.strip() for option in exercise.options],
                exercise.explanation.strip(),
            )
            for exercise in part.exercises
        ],
    )


def _check_texts(name: str, part: GrammarPart) -> None:
    if not MIN_CASES <= len(part.cases) <= MAX_CASES:
        raise ValueError(f"{name}: give {MIN_CASES} to {MAX_CASES} cases")
    texts = {
        "example": part.example,
        **{f"case {n}": case for n, case in enumerate(part.cases, 1)},
    }
    for field, text in texts.items():
        if not text:
            raise ValueError(f"{name}: the {field} is empty")
        if len(text) > MAX_SENTENCE_LENGTH:
            raise ValueError(
                f"{name}: the {field} is too long; use at most "
                f"{MAX_SENTENCE_LENGTH} characters"
            )
        if len(text.splitlines()) > 1:
            raise ValueError(f"{name}: the {field} must be one line")
    if not MIN_EXERCISES <= len(part.exercises) <= MAX_EXERCISES:
        raise ValueError(f"{name}: give {MIN_EXERCISES} to {MAX_EXERCISES} exercises")
    solved = set()
    for n, exercise in enumerate(part.exercises, 1):
        check_exercise(f"{name}: exercise {n}", _stock_form(part.topic_id, exercise))
        text = _solved(exercise)
        if text in solved:
            raise ValueError(f"{name}: exercise {n} is in the Lesson twice")
        solved.add(text)
    if not part.rule:
        raise ValueError(f"{name}: the rule is empty")
    if len(part.rule) > MAX_RULE_LENGTH:
        raise ValueError(
            f"{name}: the rule is too long; use at most {MAX_RULE_LENGTH} characters"
        )


def _stock_form(topic_id: str, exercise: LessonExercise) -> Exercise:
    return Exercise(
        topic_id,
        exercise.kind,
        exercise.sentence,
        exercise.answer,
        exercise.options,
        exercise.explanation,
    )


def _solved(exercise: LessonExercise) -> str:
    """The exercise sentence with the answer in the gap."""
    return exercise.sentence.replace(GAP, exercise.answer)


def _check_sentences_stored(store: VocabStore, words: list[LessonWord]) -> None:
    """Each word needs its sentences; one on the list for the learner is left out."""
    for word in words:
        stored = store.example_sentences(word.base_form)
        for number in range(1, SENTENCES_PER_WORD + 1):
            if number in stored:
                continue
            if store.failed_tries(word.base_form, number) > MAX_RETRIES:
                continue
            raise ValueError(
                f"Sentence {number} of {word.base_form!r} is not stored yet: "
                "store it with add_sentences first"
            )


def _check_with_language_tool(checker: SentenceChecker, topics: list[dict]) -> None:
    """The German sentences an agent wrote must pass LanguageTool, like any other."""
    texts = [
        text
        for topic in topics
        for text in [
            topic["example"],
            *topic["cases"],
            *(
                exercise["sentence"].replace(GAP, exercise["answer"])
                for exercise in topic["exercises"]
            ),
        ]
    ]
    found = [
        f"{text!r}: {'; '.join(problems)}"
        for text, problems in zip(texts, checker.check(texts))
        if problems
    ]
    if found:
        raise ValueError(
            "LanguageTool found problems; write new sentences for them: "
            + " | ".join(found)
        )


def _clean(text: str) -> str:
    return _MARKUP.sub("", text)


def _texts_of(line: Line) -> list[str]:
    """The full text of a Line and each of its rows (one row per speaker)."""
    text = _clean(line.text)
    return [text, *text.splitlines()]


def _plain(text: str) -> str:
    """The words of a text in lower case, to compare texts."""
    return " ".join(_WORD.findall(text.lower()))


def _has_word(text: str, name: str) -> bool:
    """Whether the text uses the name, also with a genitive ending: "Marthas"."""
    return re.search(rf"(?<!\w){re.escape(name)}(?:s|')?(?!\w)", text) is not None


def _word(word: LessonWord, store: VocabStore, facts: WordFacts) -> dict:
    found = asdict(facts.lookup(word.base_form, word.word_type))
    sentences = store.example_sentences(word.base_form)
    return {
        "base_form": word.base_form,
        "word_type": word.word_type,
        "seen_form": word.seen_form,
        "line": word.line.number,
        "meaning": found["meaning"],
        "meaning_status": found["meaning_status"],
        "gender": found["gender"],
        "plural": found["plural"],
        "verb_forms": found["verb_forms"],
        "parts": found["parts"],
        "sentences": [sentences[number] for number in sorted(sentences)],
        "exercises": _article_exercises(word.base_form, found["gender"]),
    }


def _article_exercises(base_form: str, gender: str | None) -> list[dict]:
    """A der/die/das exercise for a noun with a gender; none for other words."""
    if gender not in ARTICLES:
        return []
    article = ARTICLES[gender]
    return [
        {
            "id": f"{base_form}:article",
            "kind": ARTICLE_KIND,
            "sentence": f"{GAP} {base_form}",
            "answer": article,
            "options": list(ARTICLES.values()),
            "explanation": f"{base_form} is {gender}: {article} {base_form}.",
        }
    ]
