"""Subtitle tagger: a copy of an Episode's .srt with Tags for its Lesson.

A Tag is a short note in square brackets at the end of a Line. A word Tag
names a Taught word by its Base form, on the first 2 Lines where it is heard.
A grammar Tag names a Grammar topic, on the Lines the Lesson used for it.
A film's tagged .srt has the whole film, but Tags go only on the Lines of
the Episode the Lesson is for.
Tags never show a meaning: the learner must still recall it.
"""

from dataclasses import replace
from pathlib import Path

from core.episode import Episode, as_episode, episode_videos, subtitle_file
from core.subtitles import GERMAN_LANGUAGES, TAGGED_SUFFIX, Line, read_lines, write_lines
from core.word_analysis import analyse_all

TAG_LINES = 2


def tagged_subtitles_path(episode: Episode | Path | str) -> Path:
    """Where the tagged .srt of an Episode goes: next to its video.

    Its name is the video's base name plus ".de.tagged.srt", so mpv loads it
    with sub-auto=fuzzy. A folder with no video takes the base name of its
    .srt. The Episodes of a film share one tagged .srt. ValueError if the
    folder has more than one video.
    """
    episode = as_episode(episode)
    folder = episode.folder
    videos = episode_videos(episode)
    if len(videos) > 1:
        raise ValueError(
            f"Expected one video in {folder}, found {len(videos)}: "
            "cannot name the tagged subtitles"
        )
    if videos:
        base = videos[0].stem
    else:
        base = subtitle_file(episode).stem
        name, _, language = base.rpartition(".")
        if name and language.lower() in GERMAN_LANGUAGES:
            base = name
    return folder / f"{base}.de{TAGGED_SUFFIX}"


def tag_subtitles(lesson: dict, episode: Episode | Path | str) -> Path:
    """Write the tagged .srt of a Lesson file; give its path.

    The file has every Line of the original .srt with its number and times,
    so a player shows it like the original. A word Tag goes on the first 2
    Lines each Taught word is heard in. A grammar Tag goes on the Line the
    Lesson's example comes from and on the first 2 Lines the topic was found
    in. For a film, only Lines in the Episode's time range get Tags. A new
    call replaces the file, also the one of another Episode of the film.
    """
    episode = as_episode(episode)
    target = tagged_subtitles_path(episode)
    lines = read_lines(subtitle_file(episode))
    tags: dict[int, list[str]] = {line.number: [] for line in lines}
    taggable = {line.number for line in lines if episode.contains(line)}

    def add(number: int, tag: str) -> None:
        if number in taggable and tag not in tags[number]:
            tags[number].append(tag)

    sections = lesson["sections"]
    lines_left = {
        word["base_form"]: TAG_LINES for section in sections for word in section["words"]
    }
    own = [line for line in lines if line.number in taggable]
    for line, words in zip(own, analyse_all(line.text for line in own)):
        for base_form in dict.fromkeys(word.base_form for word in words):
            if lines_left.get(base_form, 0) > 0:
                lines_left[base_form] -= 1
                add(line.number, base_form)

    for section in sections:
        for topic in section["grammar"]:
            used = topic["lines"][:TAG_LINES]
            if topic["line"] is not None:
                used = [topic["line"], *used]
            for number in sorted(set(used)):
                add(number, topic["name"])

    return write_lines(target, [_with_tags(line, tags[line.number]) for line in lines])


def _with_tags(line: Line, tags: list[str]) -> Line:
    if not tags:
        return line
    notes = " ".join(f"[{_one_line(tag)}]" for tag in tags)
    return replace(line, text=f"{line.text} {notes}")


def _one_line(text: str) -> str:
    """A Tag on one row: a line break in a name must not split the Line."""
    return " ".join(text.split())
