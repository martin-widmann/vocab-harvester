"""Tagged subtitles: after the Lesson is built, Tags go on the Lines of a copy of the .srt."""

from datetime import timedelta
from pathlib import Path

import pytest

from core import read_lines, subtitle_file, tag_subtitles

LINES = [
    "Die Polizei sucht den Jungen in der Höhle.",
    "Er gab nicht auf.",
    "<i>Sie gibt nie auf,\nsie sucht weiter.</i>",
    "Warum gibst du auf?",
    "Ich helfe dem Mann.",
    "Wo ist die Höhle?",
]


def write_episode(folder: Path, texts: list[str], name: str = "Episode.de.srt") -> Path:
    blocks = []
    for number, text in enumerate(texts, start=1):
        start = timedelta(seconds=10 * number)
        end = start + timedelta(seconds=2, milliseconds=250)
        blocks.append(f"{number}\n{_time(start)} --> {_time(end)}\n{text}\n")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text("\n".join(blocks), encoding="utf-8")
    return folder


def _time(at: timedelta) -> str:
    milliseconds = int(at.total_seconds() * 1000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02},{milliseconds:03}"


def word(base_form: str, meaning: str) -> dict:
    return {"base_form": base_form, "word_type": "X", "meaning": meaning}


def topic(name: str, lines: list[int], line: int | None = None) -> dict:
    return {"topic_id": name.lower(), "name": name, "line": line, "lines": lines}


def lesson(words=(), grammar=()) -> dict:
    return {
        "schema_version": 1,
        "number": 1,
        "episode": "Test/S01E01",
        "sections": [
            {"number": 1, "words": list(words), "grammar": list(grammar)},
            {"number": 2, "words": [], "grammar": []},
            {"number": 3, "words": [], "grammar": []},
        ],
    }


@pytest.fixture
def folder(tmp_path):
    return write_episode(tmp_path / "Test" / "S01E01", LINES)


def texts(path: Path) -> list[str]:
    return [line.text for line in read_lines(path)]


def test_a_word_tag_with_the_base_form_goes_on_the_first_2_lines_of_each_taught_word(folder):
    path = tag_subtitles(
        lesson(words=[word("aufgeben", "to give up"), word("Höhle", "cave")]), folder
    )

    assert texts(path) == [
        "Die Polizei sucht den Jungen in der Höhle. [Höhle]",
        "Er gab nicht auf. [aufgeben]",
        "<i>Sie gibt nie auf,\nsie sucht weiter.</i> [aufgeben]",
        "Warum gibst du auf?",
        "Ich helfe dem Mann.",
        "Wo ist die Höhle? [Höhle]",
    ]


def test_a_grammar_tag_goes_only_on_the_lines_the_lesson_used(folder):
    path = tag_subtitles(lesson(grammar=[topic("Dativ", [5], line=5)]), folder)

    assert texts(path) == [*LINES[:4], "Ich helfe dem Mann. [Dativ]", LINES[5]]


def test_a_grammar_tag_goes_on_the_example_line_and_the_first_2_found_lines(folder):
    path = tag_subtitles(lesson(grammar=[topic("Dativ", [1, 2, 4, 5], line=5)]), folder)

    tagged = [number for number, text in enumerate(texts(path), 1) if "[Dativ]" in text]
    assert tagged == [1, 2, 5]


def test_a_line_with_a_word_and_a_grammar_topic_gets_both_tags(folder):
    path = tag_subtitles(
        lesson(
            words=[word("helfen", "to help")],
            grammar=[topic("Dativ", [5]), topic("Perfekt", [5])],
        ),
        folder,
    )

    assert texts(path)[4] == "Ich helfe dem Mann. [helfen] [Dativ] [Perfekt]"


def test_tags_never_show_the_meaning(folder):
    path = tag_subtitles(
        lesson(words=[word("aufgeben", "to give up"), word("Höhle", "cave")]), folder
    )

    content = path.read_text(encoding="utf-8")
    assert "give up" not in content
    assert "cave" not in content


def test_the_tagged_file_keeps_every_line_with_its_number_and_times(folder):
    original = read_lines(subtitle_file(folder))

    path = tag_subtitles(lesson(words=[word("aufgeben", "to give up")]), folder)

    tagged = read_lines(path)
    assert [(line.number, line.start, line.end) for line in tagged] == [
        (line.number, line.start, line.end) for line in original
    ]


def test_the_tagged_file_is_saved_next_to_the_video_with_its_base_name(tmp_path):
    folder = write_episode(tmp_path / "Dark" / "S01E03", LINES, name="subs.srt")
    (folder / "Dark.S01E03.mkv").write_bytes(b"")

    path = tag_subtitles(lesson(), folder)

    assert path == folder / "Dark.S01E03.de.tagged.srt"
    assert path.is_file()


def test_with_no_video_the_tagged_file_takes_the_base_name_of_the_srt(folder):
    path = tag_subtitles(lesson(), folder)

    assert path == folder / "Episode.de.tagged.srt"


def test_the_tagged_file_is_not_taken_for_the_original_srt(folder):
    original = subtitle_file(folder)

    tag_subtitles(lesson(words=[word("aufgeben", "to give up")]), folder)
    tag_subtitles(lesson(words=[word("Höhle", "cave")]), folder)

    assert subtitle_file(folder) == original
    assert texts(folder / "Episode.de.tagged.srt")[1] == "Er gab nicht auf."
