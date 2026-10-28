"""Subtitles: read an .srt file into Lines."""

import re
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
