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

_SUBTITLE_STREAM = re.compile(
    r"Stream #0:(\d+)(?:\[\w+\])?(?:\(([\w-]+)\))?: Subtitle: (\w+)"
)


class SubtitleError(ValueError):
    """Subtitles that cannot be read or extracted."""


def extract_subtitles(video_path: Path | str, srt_path: Path | str) -> Path:
    """Extract the German subtitle track of a video container to an .srt file."""
    video = Path(video_path)
    target = Path(srt_path)
    ffmpeg = _ffmpeg()
    track = _german_track(ffmpeg, video)
    handle, part = tempfile.mkstemp(suffix=".part", dir=target.parent)
    os.close(handle)
    try:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
             "-map", f"0:{track}", "-c:s", "srt", "-f", "srt", part],
            capture_output=True,
        )
        if result.returncode != 0:
            raise SubtitleError(
                f"ffmpeg could not extract subtitles from {video.name}: "
                f"{_last_line(result.stderr)}"
            )
        os.replace(part, target)
    finally:
        Path(part).unlink(missing_ok=True)
    return target


def _german_track(ffmpeg: str, video: Path) -> int:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(video)], capture_output=True
    )
    listing = result.stderr.decode("utf-8", errors="replace")
    if "Input #0" not in listing:
        raise SubtitleError(f"ffmpeg could not read {video.name}: {_last_line(result.stderr)}")
    for index, language, _codec in _SUBTITLE_STREAM.findall(listing):
        if language.lower() in GERMAN_LANGUAGES:
            return int(index)
    raise SubtitleError(f"No German subtitle track in {video.name}")


def _ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
    except ImportError:
        raise SubtitleError("ffmpeg is not installed, so subtitles cannot be extracted")
    return imageio_ffmpeg.get_ffmpeg_exe()


def _last_line(stderr: bytes) -> str:
    lines = stderr.decode("utf-8", errors="replace").strip().splitlines()
    return lines[-1] if lines else "no message"
