"""Web server: the learner's door to the core. It holds no domain logic."""

from contextlib import closing
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core import (
    Curriculum,
    Grader,
    GraderError,
    LessonFiles,
    NewWord,
    SystemDateClock,
    VocabStore,
    check_answer,
    due_cards,
    find_episode,
    finish_lesson,
    grade_card,
    lesson_for_page,
    new_words,
    record_answer,
)
from core.claude_grader import ClaudeGrader
from core.language_tool import LanguageTool, SystemClock
from core.review import Clock
from core.sentences import SentenceChecker

PAGE = Path(__file__).parent / "page.html"
APP_TITLE = "German Media Learning"


class Answer(BaseModel):
    base_form: str
    word_type: str
    key: str


class LessonAnswer(BaseModel):
    exercise_id: str
    answer: str


class Grade(BaseModel):
    base_form: str
    rating: str
    article: str | None = None


def create_app(
    media_root: Path,
    db_path: Path,
    grader: Grader | None = None,
    clock: Clock | None = None,
) -> FastAPI:
    """The web server. `grader` checks open answers; by default the grader agent.

    One grader for the whole server, so the LanguageTool rate limit holds
    across answers. `clock` gives the review dates; by default the computer's.
    """
    app = FastAPI(title=APP_TITLE)
    if grader is None:
        grader = Grader(ClaudeGrader(), SentenceChecker(LanguageTool(), SystemClock()))
    if clock is None:
        clock = SystemDateClock()

    @app.get("/", include_in_schema=False)
    def page() -> FileResponse:
        return FileResponse(PAGE)

    @app.get("/api/check")
    def words_to_check(episode: str) -> list[dict]:
        try:
            with closing(VocabStore(db_path)) as store:
                words = new_words(find_episode(media_root, episode), store)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error))
        return [asdict(word) for word in words]

    @app.post("/api/check/answers")
    def answer(answer: Answer) -> dict:
        word = NewWord(answer.base_form, answer.word_type)
        try:
            with closing(VocabStore(db_path)) as store:
                state = record_answer(store, word, answer.key)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error))
        return {"state": state.value}

    @app.get("/api/lessons")
    def lessons() -> list[dict]:
        return [asdict(info) for info in LessonFiles.next_to(db_path).lessons()]

    @app.get("/api/lessons/{number}")
    def lesson(number: int) -> dict:
        try:
            return lesson_for_page(LessonFiles.next_to(db_path), number)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error))

    @app.post("/api/lessons/{number}/answers")
    def lesson_answer(number: int, answer: LessonAnswer) -> dict:
        try:
            result = check_answer(
                LessonFiles.next_to(db_path),
                number,
                answer.exercise_id,
                answer.answer,
                grader=grader,
            )
        except GraderError as error:
            raise HTTPException(status_code=503, detail=str(error))
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error))
        return asdict(result)

    @app.post("/api/lessons/{number}/finish")
    def finish(number: int) -> dict:
        try:
            with (
                closing(VocabStore(db_path)) as store,
                closing(Curriculum(db_path)) as curriculum,
            ):
                finished = finish_lesson(
                    LessonFiles.next_to(db_path),
                    number,
                    store=store,
                    curriculum=curriculum,
                    today=clock.now().date(),
                )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error))
        return {
            "number": finished.number,
            "taught_words": finished.taught_words,
            "topics": [
                {**asdict(topic), "state": topic.state.value} for topic in finished.topics
            ],
        }

    @app.get("/api/reviews")
    def reviews() -> list[dict]:
        with closing(VocabStore(db_path)) as store:
            return [asdict(card) for card in due_cards(store, clock)]

    @app.post("/api/reviews")
    def grade(grade: Grade) -> dict:
        try:
            with closing(VocabStore(db_path)) as store:
                graded = grade_card(
                    store, grade.base_form, grade.rating, clock, article=grade.article
                )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error))
        return {
            "base_form": graded.base_form,
            "rating": graded.rating,
            "due": graded.due.isoformat(),
            "article": None if graded.article is None else asdict(graded.article),
        }

    return app
