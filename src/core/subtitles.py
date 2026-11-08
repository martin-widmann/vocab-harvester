"""Subtitles: read an .srt file into Lines; extract one from a video."""

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

_TIMES = re.compile(
    r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)"
)


@dataclass(frozen=True)
class Line:
    """One subtitle entry of an Episode, with its start and end time."""

    number: int
    start: timedelta
    end: timedelta
    text: str


def read_lines(srt_path: Path | str) -> list[Line]:
    """Read an .srt file into Lines, in file order."""
    content = Path(srt_path).read_text(encoding="utf-8-sig")
    blocks = re.split(r"\n\s*\n", content.replace("\r\n", "\n").strip())
    return [line for line in map(_parse_block, blocks) if line is not None]


def _parse_block(block: str) -> Line | None:
    rows = block.strip().split("\n")
    if len(rows) < 3 or not rows[0].strip().isdigit():
        return None
    times = _TIMES.search(rows[1])
    if times is None:
        return None
    h1, m1, s1, ms1, h2, m2, s2, ms2 = (int(t) for t in times.groups())
    return Line(
        number=int(rows[0]),
        start=timedelta(hours=h1, minutes=m1, seconds=s1, milliseconds=ms1),
        end=timedelta(hours=h2, minutes=m2, seconds=s2, milliseconds=ms2),
        text="\n".join(rows[2:]),
    )


GERMAN_LANGUAGES = frozenset({"de", "deu", "ger"})
VIDEO_SUFFIXES = frozenset({".mkv", ".mp4", ".m4v", ".mov", ".webm"})
IMAGE_CODECS = frozenset(
    {"hdmv_pgs_subtitle", "dvd_subtitle", "dvb_subtitle", "xsub"}
)
LIST_TIMEOUT = 60
EXTRACT_TIMEOUT = 600

_SUBTITLE_STREAM = re.compile(
    r"Stream #0:(\d+)(?:\[\w+\])?(?:\(([\w-]+)\))?: Subtitle: (\w+)(.*)"
)
# Keep ffmpeg from opening a console window when started on Windows.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class SubtitleError(ValueError):
    """Subtitles that cannot be read or extracted."""


@dataclass(frozen=True)
class _Track:
    index: int
    codec: str
    forced: bool


def extract_subtitles(video_path: Path | str, srt_path: Path | str) -> Path:
    """Extract the German subtitle track of a video container to an .srt file.

    A full German text track is taken before a forced one (a forced track
    only holds the foreign-language parts).
    """
    video = Path(video_path)
    target = Path(srt_path)
    ffmpeg = _ffmpeg()
    track = _german_track(ffmpeg, video)
    try:
        handle, temp_srt = tempfile.mkstemp(suffix=".part", dir=target.parent)
        os.close(handle)
    except OSError as error:
        raise SubtitleError(f"Cannot write subtitles next to {video.name}: {error}") from error
    try:
        result = _run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
             "-map", f"0:{track.index}", "-c:s", "srt", "-f", "srt", temp_srt],
            EXTRACT_TIMEOUT,
        )
        if result.returncode != 0:
            raise SubtitleError(
                f"ffmpeg could not extract subtitles from {video.name}: "
                f"{_last_line(result.stderr)}"
            )
        os.replace(temp_srt, target)
    except OSError as error:
        raise SubtitleError(f"Cannot write subtitles next to {video.name}: {error}") from error
    finally:
        Path(temp_srt).unlink(missing_ok=True)
    return target


def _german_track(ffmpeg: str, video: Path) -> _Track:
    result = _run([ffmpeg, "-hide_banner", "-i", str(video)], LIST_TIMEOUT)
    listing = _text(result.stderr)
    if "Input #0" not in listing:
        raise SubtitleError(f"ffmpeg could not read {video.name}: {_last_line(result.stderr)}")
    german = [
        _Track(int(index), codec, "(forced)" in rest)
        for index, language, codec, rest in _SUBTITLE_STREAM.findall(listing)
        if language.lower().split("-")[0] in GERMAN_LANGUAGES
    ]
    if not german:
        raise SubtitleError(f"No German subtitle track in {video.name}")
    text_tracks = [track for track in german if track.codec not in IMAGE_CODECS]
    if not text_tracks:
        raise SubtitleError(
            f"The German subtitle track in {video.name} is an image format "
            f"({german[0].codec}), so it cannot be turned into text"
        )
    return min(text_tracks, key=lambda track: track.forced)


def _run(command: list[str], timeout: int) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            command, capture_output=True, timeout=timeout, creationflags=_NO_WINDOW
        )
    except subprocess.TimeoutExpired as error:
        raise SubtitleError(f"ffmpeg did not finish within {timeout} seconds") from error
    except OSError as error:
        raise SubtitleError(f"Cannot start ffmpeg: {error}") from error


def _ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as error:
        raise SubtitleError(
            "ffmpeg is not installed, so subtitles cannot be extracted"
        ) from error


def _text(output: bytes) -> str:
    return output.decode("utf-8", errors="replace")


def _last_line(stderr: bytes) -> str:
    lines = _text(stderr).strip().splitlines()
    return lines[-1] if lines else "no message"
