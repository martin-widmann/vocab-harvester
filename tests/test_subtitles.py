from datetime import timedelta
from pathlib import Path

from core import read_lines

EPISODE = Path(__file__).parent / "fixtures" / "Dark" / "S01E01"
SRT = EPISODE / "Dark.S01E01.de.srt"


def test_srt_is_read_into_lines_with_start_and_end_times():
    lines = read_lines(SRT)

    assert len(lines) == 4
    first = lines[0]
    assert first.number == 1
    assert first.start == timedelta(seconds=1)
    assert first.end == timedelta(seconds=3, milliseconds=500)
    assert first.text == "Äh, wo ist Mikkel?"


def test_a_line_over_two_rows_keeps_both_rows():
    lines = read_lines(SRT)

    assert lines[1].text == "<i>Die Polizei sucht\nden Jungen in der Höhle.</i>"
    assert lines[3].end == timedelta(seconds=12, milliseconds=750)
