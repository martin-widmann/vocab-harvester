import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

from core import SubtitleError, VocabStore, new_words, subtitle_file
from core.cli import main
from mcp_server.tools import ToolError, Toolbox
from web.server import create_app

FIXTURES = Path(__file__).parent / "fixtures" / "Dark"
GERMAN_SRT = FIXTURES / "S01E01" / "Dark.S01E01.de.srt"
OTHER_SRT = FIXTURES / "S01E02" / "Dark.S01E02.de.srt"


def _ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    imageio_ffmpeg = pytest.importorskip("imageio_ffmpeg")
    return imageio_ffmpeg.get_ffmpeg_exe()


def make_video(
    path: Path, tracks: list[tuple[Path, str]], forced: tuple[int, ...] = ()
) -> Path:
    """Build a video container whose subtitle tracks are the given .srt files.

    Each track is (srt file, language code), in track order. The tracks with
    an index in `forced` are marked as forced.
    """
    command = [_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y"]
    for srt, _ in tracks:
        command += ["-i", str(srt)]
    for index in range(len(tracks)):
        command += ["-map", str(index)]
    command += ["-c:s", "srt"]
    for index, (_, language) in enumerate(tracks):
        command += [f"-metadata:s:s:{index}", f"language={language}"]
        if index in forced:
            command += [f"-disposition:s:{index}", "forced"]
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(command + [str(path)], check=True)
    return path


def test_an_episode_with_only_an_mkv_gives_the_same_new_words_as_its_srt(tmp_path):
    episode = tmp_path / "Dark" / "S01E01"
    make_video(
        episode / "Dark.S01E01.mkv",
        [(OTHER_SRT, "eng"), (GERMAN_SRT, "ger")],
    )
    store = VocabStore(tmp_path / "vocab.sqlite")

    assert new_words(episode, store) == new_words(GERMAN_SRT.parent, store)


def test_a_video_with_no_german_subtitle_track_gives_a_clear_error(tmp_path):
    episode = tmp_path / "Dark" / "S01E01"
    make_video(episode / "Dark.S01E01.mkv", [(OTHER_SRT, "eng"), (GERMAN_SRT, "fre")])

    with pytest.raises(ValueError, match="No German subtitle track in Dark.S01E01.mkv"):
        subtitle_file(episode)
    assert not list(episode.glob("*.srt"))


def test_the_extracted_srt_is_kept_next_to_the_video_and_used_again(tmp_path):
    episode = tmp_path / "Dark" / "S01E01"
    video = make_video(episode / "Dark.S01E01.mkv", [(GERMAN_SRT, "deu")])

    extracted = subtitle_file(episode)
    video.unlink()

    assert extracted == episode / "Dark.S01E01.srt"
    assert subtitle_file(episode) == extracted
    assert [path.name for path in episode.iterdir()] == ["Dark.S01E01.srt"]


def test_a_tagged_srt_does_not_stop_the_extraction(tmp_path):
    episode = tmp_path / "Dark" / "S01E01"
    make_video(episode / "Dark.S01E01.mkv", [(GERMAN_SRT, "ger")])
    (episode / "Dark.S01E01.tagged.srt").write_text("", encoding="utf-8")

    assert subtitle_file(episode) == episode / "Dark.S01E01.srt"


def test_a_folder_with_no_srt_and_no_video_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="found no .srt and 0 videos"):
        subtitle_file(tmp_path)


def test_a_full_german_text_track_is_taken_over_a_forced_one(tmp_path):
    episode = tmp_path / "Dark" / "S01E01"
    make_video(
        episode / "Dark.S01E01.mkv",
        [(OTHER_SRT, "ger"), (GERMAN_SRT, "de-DE")],
        forced=(0,),
    )
    store = VocabStore(tmp_path / "vocab.sqlite")

    assert new_words(episode, store) == new_words(GERMAN_SRT.parent, store)


def test_a_missing_episode_folder_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        subtitle_file(tmp_path / "S09E09")


def test_the_new_words_command_shows_the_error_without_a_traceback(tmp_path, capsys):
    episode = tmp_path / "Dark" / "S01E01"
    make_video(episode / "Dark.S01E01.mkv", [(GERMAN_SRT, "eng")])

    with pytest.raises(SystemExit) as stop:
        main(["new-words", str(episode), "--db", str(tmp_path / "vocab.sqlite")])

    assert stop.value.code != 0
    assert "No German subtitle track in Dark.S01E01.mkv" in capsys.readouterr().err


def test_a_video_that_ffmpeg_cannot_read_gives_a_clear_error(tmp_path):
    episode = tmp_path / "Dark" / "S01E01"
    episode.mkdir(parents=True)
    (episode / "Dark.S01E01.mkv").write_bytes(b"not a video, only a part of a download")

    with pytest.raises(SubtitleError, match="ffmpeg could not read Dark.S01E01.mkv"):
        subtitle_file(episode)
    assert not list(episode.glob("*.srt"))


def test_a_missing_ffmpeg_gives_a_clear_error(tmp_path, monkeypatch):
    episode = tmp_path / "Dark" / "S01E01"
    make_video(episode / "Dark.S01E01.mkv", [(GERMAN_SRT, "ger")])
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)

    with pytest.raises(SubtitleError, match="ffmpeg is not installed"):
        subtitle_file(episode)


BLU_RAY_LISTING = b"""\
Input #0, matroska,webm, from 'Dark.S01E01.mkv':
  Duration: 00:52:10.21, start: 0.000000, bitrate: 25000 kb/s
  Stream #0:0: Video: h264 (High), yuv420p, 1920x1080, 23.98 fps (default)
  Stream #0:1(ger): Audio: dts (DTS-HD MA), 48000 Hz, 5.1(side) (default)
  Stream #0:2(ger): Subtitle: hdmv_pgs_subtitle (pgssub) (default)
  Stream #0:3(eng): Subtitle: subrip (srt)
At least one output file must be specified
"""


def test_a_german_track_in_an_image_format_gives_a_clear_error(tmp_path, monkeypatch):
    episode = tmp_path / "Dark" / "S01E01"
    episode.mkdir(parents=True)
    (episode / "Dark.S01E01.mkv").write_bytes(b"")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **options: subprocess.CompletedProcess(
            command, 1, b"", BLU_RAY_LISTING
        ),
    )

    with pytest.raises(SubtitleError, match=r"image format \(hdmv_pgs_subtitle\)"):
        subtitle_file(episode)
    assert not list(episode.glob("*.srt"))


def test_the_mcp_door_shows_the_error_as_a_tool_error(tmp_path):
    make_video(tmp_path / "Dark" / "S01E01" / "Dark.S01E01.mkv", [(GERMAN_SRT, "eng")])
    toolbox = Toolbox(media_root=tmp_path, db_path=tmp_path / "vocab.sqlite", page=None)

    with pytest.raises(ToolError, match="No German subtitle track in Dark.S01E01.mkv"):
        toolbox.call("new_words", {"episode": "Dark/S01E01"})


def test_the_exercise_page_gets_the_error_message(tmp_path):
    make_video(tmp_path / "Dark" / "S01E01" / "Dark.S01E01.mkv", [(GERMAN_SRT, "eng")])
    app = create_app(tmp_path, tmp_path / "vocab.sqlite")
    words_to_check = next(
        route.endpoint for route in app.routes if getattr(route, "path", "") == "/api/check"
    )

    with pytest.raises(HTTPException) as refused:
        words_to_check(episode="Dark/S01E01")

    assert refused.value.status_code == 404
    assert refused.value.detail == "No German subtitle track in Dark.S01E01.mkv"


def test_hidden_mac_files_next_to_the_video_are_not_taken_as_videos(tmp_path):
    episode = tmp_path / "Dark" / "S01E01"
    make_video(episode / "Dark.S01E01.mkv", [(GERMAN_SRT, "ger")])
    (episode / "._Dark.S01E01.mkv").write_bytes(b"\x00\x05\x16\x07 Mac resource data")

    assert subtitle_file(episode) == episode / "Dark.S01E01.srt"


def test_hidden_mac_files_next_to_the_srt_are_not_taken_as_subtitles(tmp_path):
    episode = tmp_path / "Dark" / "S01E01"
    make_video(episode / "Dark.S01E01.mkv", [(GERMAN_SRT, "ger")])
    (episode / "._Dark.S01E01.mkv").write_bytes(b"\x00\x05\x16\x07 Mac resource data")
    (episode / "._Dark.S01E01.srt").write_bytes(b"\x00\x05\x16\x07 Mac resource data")
    store = VocabStore(tmp_path / "vocab.sqlite")

    assert subtitle_file(episode) == episode / "Dark.S01E01.srt"
    assert new_words(episode, store) == new_words(GERMAN_SRT.parent, store)
