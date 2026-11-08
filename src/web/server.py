"""Web server: the learner's door to the core. It holds no domain logic."""

from contextlib import closing
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core import NewWord, VocabStore, find_episode, new_words, record_answer

PAGE = Path(__file__).parent / "page.html"
APP_TITLE = "German Media Learning"


class Answer(BaseModel):
    base_form: str
    word_type: str
    key: str


def create_app(media_root: Path, db_path: Path) -> FastAPI:
    app = FastAPI(title=APP_TITLE)

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

    return app
