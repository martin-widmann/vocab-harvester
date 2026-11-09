"""Results and Finish: check the fixed answers of a Lesson, and Finish it.

A script checks gap-fill, pick-one and der/die/das answers at once against
the correct answer in the Lesson file. Each answer and its result go to the
Lesson's results file. Finish updates the learner state at once: the
Lesson's words become Taught words, and its Grammar topics become Seen, or
Learned when their Lesson exercises passed.
"""

import threading
from dataclasses import dataclass

from core.curriculum import Curriculum, TopicState
from core.grammar_topics import GAP, ExerciseKind
from core.lesson import ARTICLE_KIND, ARTICLES, LessonFiles
from core.vocab_store import VocabStore, WordState

# A Grammar topic's Lesson exercises pass when at least this share of them
# was answered right; an exercise with no answer counts as wrong.
PASS_SHARE = 2 / 3

# The web server checks answers in more than one thread: one change of a
# results file at a time.
_RESULTS_LOCK = threading.Lock()


@dataclass(frozen=True)
class Result:
    """The result of one answer: right or wrong, the correction, a short reason."""

    right: bool
    correction: str
    reason: str


@dataclass(frozen=True)
class TopicResult:
    """How a Grammar topic of a finished Lesson did, and its Topic state now."""

    topic_id: str
    right: int
    exercises: int
    passed: bool
    state: TopicState


@dataclass(frozen=True)
class Finished:
    """What Finish changed: the new Taught words and the Grammar topics."""

    number: int
    taught_words: list[str]
    topics: list[TopicResult]


def check_answer(
    lessons: LessonFiles, number: int, exercise_id: str, answer: str
) -> Result:
    """Check an answer to a fixed-answer exercise and save it to the results file.

    The first answer to an exercise stands: a new answer gives its result
    back and changes nothing. An answer that cannot be checked (a pick-one
    answer that is not an option) is rejected and not saved.
    """
    with _RESULTS_LOCK:
        lesson = lessons.read(number)
        exercise = _exercise(lesson, exercise_id)
        results = lessons.results(number)
        saved = results["answers"].get(exercise_id)
        if saved is not None:
            return Result(saved["right"], saved["correction"], saved["reason"])
        if results["finished"]:
            raise ValueError(f"Lesson {number} is finished; it takes no more answers")
        result = _checked(exercise, answer)
        results["answers"][exercise_id] = {
            "answer": answer,
            "right": result.right,
            "correction": result.correction,
            "reason": result.reason,
        }
        lessons._write_results(results)
    return result


def lesson_for_page(lessons: LessonFiles, number: int) -> dict:
    """A Lesson as the page shows it: no correct answers, with the saved results.

    The exercises lose their answer and explanation; the page gets them
    only as the result of an answer. "results" holds the saved answers and
    their results by exercise id, "finished" whether the Lesson is finished.
    """
    lesson = lessons.read(number)
    results = lessons.results(number)
    hidden = ("answer", "explanation")
    sections = [
        {
            **section,
            **{
                part: [
                    {
                        **item,
                        "exercises": [
                            {key: value for key, value in exercise.items() if key not in hidden}
                            for exercise in item.get("exercises", [])
                        ],
                    }
                    for item in section[part]
                ]
                for part in ("words", "grammar")
            },
        }
        for section in lesson["sections"]
    ]
    return {
        **lesson,
        "sections": sections,
        "results": results["answers"],
        "finished": results["finished"],
    }


def finish_lesson(
    lessons: LessonFiles,
    number: int,
    *,
    store: VocabStore,
    curriculum: Curriculum,
) -> Finished:
    """Finish a Lesson: update the learner state at once.

    Each Unknown word of the Lesson becomes a Taught word. Each Grammar topic
    becomes Seen (if it was Not seen), and Learned when its Lesson exercises
    passed; a topic further on keeps its state. A topic that left the
    Curriculum since the Lesson was written is left out. A Lesson is
    finished only once.
    """
    with _RESULTS_LOCK:
        lesson = lessons.read(number)
        results = lessons.results(number)
        if results["finished"]:
            raise ValueError(f"Lesson {number} is already finished")
        taught = []
        for section in lesson["sections"]:
            for word in section["words"]:
                if store.state_of(word["base_form"]) == WordState.UNKNOWN:
                    store.set_state(word["base_form"], WordState.TAUGHT)
                    taught.append(word["base_form"])
        in_curriculum = {status.topic.id for status in curriculum.topics()}
        topics = []
        for section in lesson["sections"]:
            for topic in section["grammar"]:
                topic_id = topic["topic_id"]
                if topic_id not in in_curriculum:
                    continue
                exercises = topic.get("exercises", [])
                right = sum(
                    1
                    for exercise in exercises
                    if results["answers"].get(exercise["id"], {}).get("right")
                )
                passed = bool(exercises) and right >= PASS_SHARE * len(exercises)
                curriculum.taught(topic_id)
                if passed:
                    curriculum.lesson_exercises_passed(topic_id)
                topics.append(
                    TopicResult(
                        topic_id,
                        right,
                        len(exercises),
                        passed,
                        _state(curriculum, topic_id),
                    )
                )
        # Last: if a step above fails, Finish can run again, as each step
        # only moves a word or a topic forward.
        results["finished"] = True
        lessons._write_results(results)
    return Finished(number, taught, topics)


def _state(curriculum: Curriculum, topic_id: str) -> TopicState:
    return next(
        status.state for status in curriculum.topics() if status.topic.id == topic_id
    )


def _exercise(lesson: dict, exercise_id: str) -> dict:
    for section in lesson["sections"]:
        for item in [*section["words"], *section["grammar"]]:
            for exercise in item.get("exercises", []):
                if exercise["id"] == exercise_id:
                    return exercise
    raise ValueError(f"Lesson {lesson['number']} has no exercise {exercise_id!r}")


def _checked(exercise: dict, answer: str) -> Result:
    expected = exercise["answer"]
    correction = exercise["sentence"].replace(GAP, expected)
    kind = exercise["kind"]
    if kind == ARTICLE_KIND:
        given = _normal(answer)
        if given not in ARTICLES.values():
            raise ValueError("Type der, die or das")
        right = given == expected
    elif kind == ExerciseKind.CHOICE.value:
        if answer not in exercise["options"]:
            raise ValueError("Pick one of " + ", ".join(exercise["options"]))
        right = answer == expected
    elif kind == ExerciseKind.GAP.value:
        right = _normal(answer) == _normal(expected)
    else:
        raise ValueError(
            f"Exercise {exercise['id']!r} is a {kind!r} exercise; a script checks "
            "only gap, choice and article exercises"
        )
    return Result(right, correction, exercise["explanation"])


def _normal(text: str) -> str:
    """A typed answer without outer and repeated spaces, in lower case."""
    return " ".join(text.split()).casefold()
