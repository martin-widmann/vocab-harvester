"""Episode: one watch unit, and the New words of it.

A series Episode is one folder, for example "Dark/S01E03". A film is one
folder with a film.json that gives the time range of each of its Episodes,
P1, P2 and maybe P3, for example "Der Film/P2". The video is never cut: a
film Episode is the Lines of the film's .srt that start in its time range.
"""

import json
import re
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from core.subtitles import TAGGED_SUFFIX, VIDEO_SUFFIXES, Line, extract_subtitles, read_lines
from core.vocab_store import VocabStore
from core.word_analysis import analyse

DEFAULT_MEDIA_ROOT = Path(__file__).resolve().parents[2] / "media"
FILM_FILE = "film.json"
FILM_CODES = ("P1", "P2", "P3")
MIN_FILM_EPISODES = 2

_TIME = re.compile(r"(\d+):([0-5]\d):([0-5]\d)")


@dataclass(frozen=True)
class Episode:
    """One watch unit: a series Episode folder, or a time range of a film.

    A series Episode has no code and covers its whole .srt. A film Episode
    has its code ("P1"-"P3") and covers the Lines that start at or after
    `start` and before `end`; an `end` of None runs to the end of the film.
    """

    folder: Path
    code: str | None = None
    start: timedelta = timedelta(0)
    end: timedelta | None = None

    @property
    def path(self) -> Path:
        """The Episode as a path: its folder, or the film folder plus its code."""
        return self.folder if self.code is None else self.folder / self.code

    def contains(self, line: Line) -> bool:
        """True if the Line starts in the Episode's time range."""
        return self.start <= line.start and (self.end is None or line.start < self.end)


@dataclass(frozen=True)
class NewWord:
    """A Base form from an Episode that is not yet in the vocab store."""

    base_form: str
    word_type: str


def as_episode(episode: "Episode | Path | str") -> Episode:
    """The Episode at a path: a series Episode folder or "<film folder>/P2".

    ValueError for a film folder itself (it is not one Episode) and for a
    code its film.json does not define.
    """
    if isinstance(episode, Episode):
        return episode
    path = Path(episode)
    film = path.parent
    if film.is_dir() and (film / FILM_FILE).is_file():
        episodes = film_episodes(film)
        code = path.name.upper()
        if code not in episodes:
            raise ValueError(
                f"The film {film.name} has no Episode {path.name!r}: "
                f"its Episodes are {', '.join(episodes)}"
            )
        return episodes[code]
    if path.is_dir():
        if (path / FILM_FILE).is_file():
            codes = ", ".join(film_episodes(path))
            raise ValueError(
                f"{path.name} is a film, not one Episode: name one of its "
                f"Episodes ({codes}), for example {path.name}/P1"
            )
        return Episode(path)
    raise ValueError(f"No Episode folder {path}")


def film_episodes(film_folder: Path | str) -> dict[str, Episode]:
    """The Episodes of a film by code, with their time ranges from its film.json.

    The file maps P1, P2 and maybe P3, in that order, to {"start": "H:MM:SS",
    "end": "H:MM:SS"}. Only the last Episode may have an "end" of null: it
    runs to the end of the film. The ranges are in order and do not overlap;
    a gap between two ranges (for example an intermission) belongs to no
    Episode. ValueError if the file breaks a rule.
    """
    folder = Path(film_folder)
    path = folder / FILM_FILE
    try:
        content = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"The film file {path} cannot be read: {error}") from error
    if not isinstance(content, dict):
        raise ValueError(
            f"The film file {path} must map each Episode code to its time range"
        )
    codes = list(content)
    if not MIN_FILM_EPISODES <= len(codes) <= len(FILM_CODES) or codes != list(
        FILM_CODES[: len(codes)]
    ):
        raise ValueError(
            f"The film file {path} must define the Episodes P1, P2 and maybe P3, "
            f"in that order; it has {', '.join(codes) or 'none'}"
        )
    episodes: dict[str, Episode] = {}
    previous_end = timedelta(0)
    for number, code in enumerate(codes, start=1):
        time_range = content[code]
        if not isinstance(time_range, dict) or set(time_range) != {"start", "end"}:
            raise ValueError(
                f"The film file {path}: {code} must be "
                '{"start": "H:MM:SS", "end": "H:MM:SS"}'
            )
        start = _time(path, code, time_range["start"])
        if number == len(codes) and time_range["end"] is None:
            end = None
        else:
            end = _time(path, code, time_range["end"])
        if start < previous_end:
            raise ValueError(
                f"The film file {path}: {code} starts before the Episode before it ends"
            )
        if end is not None and end <= start:
            raise ValueError(f"The film file {path}: {code} must end after it starts")
        episodes[code] = Episode(folder, code, start, end)
        if end is not None:
            previous_end = end
    return episodes


def _time(path: Path, name: str, value: object) -> timedelta:
    match = _TIME.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        raise ValueError(
            f"The film file {path}: {name} has the time {value!r}; write it as H:MM:SS"
        )
    hours, minutes, seconds = map(int, match.groups())
    return timedelta(hours=hours, minutes=minutes, seconds=seconds)


def episode_lines(episode: Episode | Path | str) -> list[Line]:
    """The Lines of an Episode, in file order: for a film, only its time range."""
    episode = as_episode(episode)
    return [line for line in read_lines(subtitle_file(episode)) if episode.contains(line)]


def new_words(episode: Episode | Path | str, store: VocabStore) -> list[NewWord]:
    """List the New words of an Episode, in the order they are first heard."""
    found: dict[str, NewWord] = {}
    for line in episode_lines(episode):
        for word in analyse(line.text):
            if word.base_form not in found and not store.contains(word.base_form):
                found[word.base_form] = NewWord(word.base_form, word.word_type)
    return list(found.values())


def find_episode(media_root: Path | str, name: str) -> Episode:
    """An Episode from its name, for example "Dark/S01E03" or "Der Film/P2"."""
    root = Path(media_root).resolve()
    path = (root / name).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError(f"No Episode {name!r} under {root}")
    try:
        episode = as_episode(path)
    except ValueError as error:
        raise ValueError(f"No Episode {name!r} under {root}: {error}") from error
    if episode.folder == root:
        raise ValueError(f"No Episode {name!r} under {root}")
    return episode


def match_episode(media_root: Path | str, request: str) -> str:
    """The Episode name of the media folder, from how the learner names it.

    "Dark S01E03", "dark s1e3", "Dark - S01E03" and "Dark/S01E03" all give
    "Dark/S01E03" (or "Dark/S1E3", or "Dark/S01E03 - Title", if that is the
    folder). "Der Film P2" gives "Der Film/P2". The series or film name is
    matched without case. ValueError, with the names that do exist, if there
    is no such Episode or more than one folder fits.
    """
    root = Path(media_root).resolve()
    text = " ".join(request.replace("\\", "/").split())
    match = _REQUEST.fullmatch(text)
    title, code = (match.group("title"), match.group("code")) if match else (text, None)
    folder = _title_folder(root, title.strip(_PUNCTUATION))
    if (folder / FILM_FILE).is_file():
        episodes = film_episodes(folder)
        if code is None or code.upper() not in episodes:
            raise ValueError(
                f"{folder.name} is a film: name one of its Episodes "
                f"({', '.join(episodes)}), for example {folder.name}/P1"
            )
        return f"{folder.name}/{code.upper()}"
    wanted = _season_episode(code) if code else None
    episodes = [sub.name for sub in _subfolders(folder) if _season_episode(sub.name)]
    found = [name for name in episodes if _season_episode(name) == wanted]
    if wanted is None or not found:
        raise ValueError(
            f"No Episode {request.strip()!r}: the Episodes of {folder.name} are "
            f"{', '.join(sorted(episodes)) or 'none'}"
        )
    if len(found) > 1:
        raise ValueError(
            f"{folder.name} has more than one folder for {code}: "
            f"{', '.join(sorted(found))}; keep one"
        )
    return f"{folder.name}/{found[0]}"


_PUNCTUATION = " /_,:;.-!?"
_REQUEST = re.compile(
    r"(?P<title>.+?)[\s/_,:;.\-]+(?P<code>S\d{1,2} ?E\d{1,3}|P\d)[\s.,!?]*",
    re.IGNORECASE,
)
# A series Episode folder starts with its code; a title may follow.
_SERIES_CODE = re.compile(r"S(\d{1,2}) ?E(\d{1,3})(?!\d)", re.IGNORECASE)


def _title_folder(root: Path, title: str) -> Path:
    """The series or film folder of a name: the same name, else without case."""
    folders = _subfolders(root)
    found = [folder for folder in folders if folder.name == title] or [
        folder for folder in folders if folder.name.casefold() == title.casefold()
    ]
    if not title or not found:
        names = ", ".join(sorted(folder.name for folder in folders)) or "none"
        raise ValueError(
            f"No series or film {title!r} in the media folder {root}; it has: {names}"
        )
    if len(found) > 1:
        raise ValueError(
            f"More than one folder fits {title!r}: "
            f"{', '.join(sorted(folder.name for folder in found))}; write the name exactly"
        )
    return found[0]


def _season_episode(name: str) -> tuple[int, int] | None:
    """Season and episode number of a code such as "S01E03", "s1e3" or "S01E03 - Title"."""
    match = _SERIES_CODE.match(name)
    return (int(match.group(1)), int(match.group(2))) if match else None


def _subfolders(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return [
        path for path in folder.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    ]


def episode_key(media_root: Path | str, name: str) -> str:
    """One key per Episode, however its name is written: "Dark/S01E03"."""
    root = Path(media_root).resolve()
    return find_episode(root, name).path.relative_to(root).as_posix()


def subtitle_file(episode: Episode | Path | str) -> Path:
    """The original .srt of an Episode (not the tagged one).

    The Episodes of a film share the film's one .srt. When the folder has no
    .srt but one video container, its German subtitle track is extracted to
    an .srt next to the video, once.
    """
    folder = as_episode(episode).folder
    files = _files(folder)
    srts = [
        path for path in files
        if path.suffix.lower() == ".srt"
        and not path.name.lower().endswith(TAGGED_SUFFIX)
    ]
    if len(srts) == 1:
        return srts[0]
    if srts:
        raise ValueError(f"Expected one .srt file in {folder}, found {len(srts)}")
    videos = _videos(files)
    if len(videos) != 1:
        raise ValueError(
            f"Expected one .srt file or one video in {folder}, "
            f"found no .srt and {len(videos)} videos"
        )
    return extract_subtitles(videos[0], videos[0].with_suffix(".srt"))


def episode_videos(episode: Episode | Path | str) -> list[Path]:
    """The video files of an Episode folder."""
    return _videos(_files(as_episode(episode).folder))


def _videos(files: list[Path]) -> list[Path]:
    return [path for path in files if path.suffix.lower() in VIDEO_SUFFIXES]


def _files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        raise ValueError(f"No Episode folder {folder}")
    return [
        path for path in folder.iterdir()
        # Skip hidden files, such as the "._" files macOS puts next to each file.
        if path.is_file() and not path.name.startswith(".")
    ]
