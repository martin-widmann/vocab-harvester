"""Films: a film is two or three Episodes, P1-P3, each a time range of one video.

The film folder holds the video, its .srt and a film.json with the time range
of each Episode. The video is never cut: each Episode uses only its own Lines.
"""

import json
from datetime import timedelta
from pathlib import Path

import pytest

from core import (
    FrequencyTable,
    VocabStore,
    build_frequency_table,
    episode_key,
    episode_lines,
    find_episode,
    new_words,
    pick_lesson_words,
    read_lines,
    record_answer,
    tag_subtitles,
)

FIXTURES = Path(__file__).parent / "fixtures"

RANGES = {
    "P1": {"start": "0:00:00", "end": "0:50:00"},
    "P2": {"start": "0:50:00", "end": "1:40:00"},
    "P3": {"start": "1:40:00", "end": None},
}

# One Line per (start minute, text), for a film of about 2 hours.
LINES = [
    (1, "Die Polizei sucht den Jungen in der Höhle."),  # P1
    (49.99, "Martha wartet am Bahnhof."),  # P1: it starts before 50 minutes.
    (51, "Er gab nicht auf."),  # P2, Section 1
    (70, "Wo ist die Höhle?"),  # P2, Section 2
    (80, "Ihr gebt nie auf."),  # P2, Section 3
    (90, "Sie gibt nie auf."),  # P2, Section 3
    (110, "Ich helfe dem Mann."),  # P3
]


def srt(lines: list[tuple[float, str]]) -> str:
    blocks = []
    for number, (minute, text) in enumerate(lines, start=1):
        start = timedelta(minutes=minute)
        end = start + timedelta(seconds=2)
        blocks.append(f"{number}\n{_time(start)} --> {_time(end)}\n{text}\n")
    return "\n".join(blocks)


def _time(at: timedelta) -> str:
    milliseconds = round(at.total_seconds() * 1000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02},{milliseconds:03}"


def write_film(folder: Path, ranges=RANGES, lines=LINES) -> Path:
    folder.mkdir(parents=True)
    (folder / "Der Film.mkv").write_bytes(b"not a real video")
    (folder / "Der Film.de.srt").write_text(srt(lines), encoding="utf-8")
    (folder / "film.json").write_text(json.dumps(ranges), encoding="utf-8")
    return folder


@pytest.fixture
def media(tmp_path):
    root = tmp_path / "media"
    write_film(root / "Der Film")
    return root


@pytest.fixture
def store(tmp_path):
    store = VocabStore(tmp_path / "vocab.sqlite")
    yield store
    store.close()


@pytest.fixture
def frequency(tmp_path):
    path = tmp_path / "frequency.sqlite"
    with (FIXTURES / "frequency-sample.txt").open("rb") as source:
        build_frequency_table(source, path)
    table = FrequencyTable(path)
    yield table
    table.close()


def numbers(lines) -> list[int]:
    return [line.number for line in lines]


# Finding a film Episode


def test_a_film_episode_is_found_from_the_film_name_and_its_code(media):
    episode = find_episode(media, "Der Film/P2")

    assert episode.folder == (media / "Der Film").resolve()
    assert episode.code == "P2"
    assert (episode.start, episode.end) == (timedelta(minutes=50), timedelta(minutes=100))


@pytest.mark.parametrize("name", ["Der Film/P2", "Der Film/p2", "Der Film/./P2"])
def test_a_film_episode_has_one_key_however_its_name_is_written(media, name):
    assert episode_key(media, name) == "Der Film/P2"


def test_the_last_episode_may_run_to_the_end_of_the_film(media):
    episode = find_episode(media, "Der Film/P3")

    assert (episode.start, episode.end) == (timedelta(minutes=100), None)


def test_a_film_itself_is_not_an_episode(media):
    with pytest.raises(ValueError, match="P1"):
        find_episode(media, "Der Film")


def test_an_episode_code_the_film_does_not_define_is_rejected(media):
    with pytest.raises(ValueError):
        find_episode(media, "Der Film/P4")


def test_a_folder_named_like_a_film_episode_does_not_hide_its_time_range(media):
    (media / "Der Film" / "P2").mkdir()

    episode = find_episode(media, "Der Film/P2")

    assert (episode.folder, episode.code) == ((media / "Der Film").resolve(), "P2")


def test_a_series_episode_still_covers_its_whole_srt():
    episode = find_episode(FIXTURES, "Dark/S01E01")

    assert episode.code is None
    assert numbers(episode_lines(episode)) == numbers(
        read_lines(FIXTURES / "Dark" / "S01E01" / "Dark.S01E01.de.srt")
    )


@pytest.mark.parametrize(
    "ranges",
    [
        {"P1": {"start": "0:00:00", "end": "0:50:00"}},  # Only one Episode.
        {**RANGES, "P4": {"start": "2:00:00", "end": None}},  # More than 3 Episodes.
        {"P1": RANGES["P1"], "P3": RANGES["P3"]},  # An Episode is missing.
        {"P1": {"start": "0:00:00", "end": "0:50:00"}, "P2": {"start": "0:40:00", "end": None}},
        {"P1": {"start": "0:30:00", "end": "0:10:00"}, "P2": {"start": "0:50:00", "end": None}},
        {"P1": {"start": "0:00:00", "end": None}, "P2": {"start": "0:50:00", "end": None}},
        {"P1": {"start": "zero", "end": "0:50:00"}, "P2": {"start": "0:50:00", "end": None}},
        {"P1": {"start": "0:00:00", "end": "0:70:00"}, "P2": {"start": "1:10:00", "end": None}},
        {"P1": ["0:00:00", "0:50:00"], "P2": ["0:50:00", None]},
        ["P1", "P2"],
    ],
)
def test_a_film_file_that_breaks_a_rule_is_rejected(tmp_path, ranges):
    write_film(tmp_path / "media" / "Film", ranges=ranges)

    with pytest.raises(ValueError):
        find_episode(tmp_path / "media", "Film/P1")


def test_a_film_file_that_is_not_json_is_rejected(tmp_path):
    folder = write_film(tmp_path / "media" / "Film")
    (folder / "film.json").write_text("{P1: 0-50}", encoding="utf-8")

    with pytest.raises(ValueError):
        find_episode(tmp_path / "media", "Film/P1")


# Lines, New words and Sections of a film Episode


def test_an_episode_has_only_the_lines_that_start_in_its_time_range(media):
    assert numbers(episode_lines(find_episode(media, "Der Film/P1"))) == [1, 2]
    assert numbers(episode_lines(find_episode(media, "Der Film/P2"))) == [3, 4, 5, 6]
    assert numbers(episode_lines(find_episode(media, "Der Film/P3"))) == [7]


def test_new_words_come_only_from_the_lines_of_the_episode(media, store, tmp_path):
    only_p2 = tmp_path / "only P2"
    only_p2.mkdir()
    (only_p2 / "p2.srt").write_text(srt(LINES[2:6]), encoding="utf-8")

    words = new_words(find_episode(media, "Der Film/P2"), store)

    assert words == new_words(only_p2, store)
    assert "Höhle" in [word.base_form for word in words]
    assert "Polizei" not in [word.base_form for word in words]
    assert "helfen" not in [word.base_form for word in words]


def test_lesson_words_come_from_the_episode_with_sections_from_its_start(
    media, store, frequency
):
    episode = find_episode(media, "Der Film/P2")
    for word in new_words(episode, store):
        record_answer(store, word, "U" if word.base_form in {"aufgeben", "Höhle"} else "K")
    # Unknown in P1 and P3 only: never picked for P2.
    for word in new_words(find_episode(media, "Der Film/P1"), store):
        record_answer(store, word, "U")
    for word in new_words(find_episode(media, "Der Film/P3"), store):
        record_answer(store, word, "U")

    picked = {word.base_form: word for word in pick_lesson_words(episode, store, frequency)}

    assert set(picked) == {"aufgeben", "Höhle"}
    assert (picked["aufgeben"].line.number, picked["aufgeben"].section) == (3, 1)
    assert (picked["Höhle"].line.number, picked["Höhle"].section) == (4, 2)


# The tagged .srt of a film Episode


def lesson(words=(), grammar=()) -> dict:
    return {
        "schema_version": 1,
        "number": 1,
        "episode": "Der Film/P2",
        "sections": [
            {"number": 1, "words": list(words), "grammar": list(grammar)},
            {"number": 2, "words": [], "grammar": []},
            {"number": 3, "words": [], "grammar": []},
        ],
    }


def test_the_tagged_srt_covers_the_whole_film_but_tags_only_lines_of_the_episode(media):
    words = [
        {"base_form": "Höhle", "word_type": "NOUN", "meaning": "cave"},
        {"base_form": "aufgeben", "word_type": "VERB", "meaning": "to give up"},
    ]
    dativ = {"topic_id": "dativ", "name": "Dativ", "line": 7, "lines": [1, 4]}

    path = tag_subtitles(lesson(words, [dativ]), find_episode(media, "Der Film/P2"))

    assert path == (media / "Der Film" / "Der Film.de.tagged.srt").resolve()
    assert [line.text for line in read_lines(path)] == [
        "Die Polizei sucht den Jungen in der Höhle.",
        "Martha wartet am Bahnhof.",
        "Er gab nicht auf. [aufgeben]",
        "Wo ist die Höhle? [Höhle] [Dativ]",
        "Ihr gebt nie auf. [aufgeben]",
        "Sie gibt nie auf.",
        "Ich helfe dem Mann.",
    ]
