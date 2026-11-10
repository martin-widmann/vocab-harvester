"""Subtitle tagger: a copy of an Episode's .srt with Tags for its Lesson.

A Tag is a short note in square brackets at the end of a Line. A word Tag
names a Taught word by its Base form, on the first 2 Lines where it is heard.
A grammar Tag names a Grammar topic, on the Lines the Lesson used for it.
Tags never show a meaning: the learner must still recall it.
"""

import re
from dataclasses import replace
from pathlib import Path

from core.episode import subtitle_file
from core.subtitles import VIDEO_SUFFIXES, Line, read_lines, write_lines
from core.word_analysis import analyse_all

WORD_TAG_LINES = 2
TAGGED_SUFFIX = ".de.tagged.srt"

_LANGUAGE_SUFFIX = re.compile(r"\.(de|deu|ger)$", re.IGNORECASE)


def tag_subtitles(lesson: dict, episode_folder: Path | str) -> Path:
    """Write the tagged .srt of a Lesson file next to the video; give its path.

    The file has every Line of the original .srt with its number and times,
    so a player shows it like the original. Its name is the video's base name
    plus ".de.tagged.srt", so mpv loads it with sub-auto=fuzzy. A folder with
    no video takes the base name of its .srt. A new call replaces the file.
    """
    folder = Path(episode_folder)
    source = subtitle_file(folder)
    lines = read_lines(source)
    tags: dict[int, list[str]] = {line.number: [] for line in lines}

    sections = lesson["sections"]
    taught = [word["base_form"] for section in sections for word in section["words"]]
    tagged_lines = {base_form: 0 for base_form in taught}
    for line, words in zip(lines, analyse_all(line.text for line in lines)):
        heard = dict.fromkeys(word.base_form for word in words)
        for base_form in heard:
            if tagged_lines.get(base_form, WORD_TAG_LINES) < WORD_TAG_LINES:
                tagged_lines[base_form] += 1
                tags[line.number].append(base_form)

    for section in sections:
        for topic in section["grammar"]:
            for number in topic["lines"]:
                if number in tags and topic["name"] not in tags[number]:
                    tags[number].append(topic["name"])

    tagged = [_with_tags(line, tags[line.number]) for line in lines]
    return write_lines(_tagged_path(folder, source), tagged)


def _with_tags(line: Line, tags: list[str]) -> Line:
    if not tags:
        return line
    notes = " ".join(f"[{_one_line(tag)}]" for tag in tags)
    return replace(line, text=f"{line.text} {notes}")


def _one_line(text: str) -> str:
    """A Tag on one row: a line break in a name must not split the Line."""
    return " ".join(text.split())


def _tagged_path(folder: Path, source: Path) -> Path:
    videos = [
        path
        for path in folder.iterdir()
        if path.is_file()
        and not path.name.startswith(".")
        and path.suffix.lower() in VIDEO_SUFFIXES
    ]
    if len(videos) > 1:
        raise ValueError(
            f"Expected one video in {folder}, found {len(videos)}: "
            "cannot name the tagged subtitles"
        )
    base = videos[0].stem if videos else _LANGUAGE_SUFFIX.sub("", source.stem)
    return folder / f"{base}{TAGGED_SUFFIX}"
