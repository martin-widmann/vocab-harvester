import shutil
import subprocess
from pathlib import Path

import pytest

from core import VocabStore, new_words, subtitle_file

FIXTURES = Path(__file__).parent / "fixtures" / "Dark"
GERMAN_SRT = FIXTURES / "S01E01" / "Dark.S01E01.de.srt"
OTHER_SRT = FIXTURES / "S01E02" / "Dark.S01E02.de.srt"


def _ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    imageio_ffmpeg = pytest.importorskip("imageio_ffmpeg")
    return imageio_ffmpeg.get_ffmpeg_exe()


def make_video(path: Path, tracks: list[tuple[Path, str]]) -> Path:
    """Build a video container whose subtitle tracks are the given .srt files.

    Each track is (srt file, language code), in track order.
    """
    command = [_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y"]
    for srt, _ in tracks:
        command += ["-i", str(srt)]
    for index in range(len(tracks)):
        command += ["-map", str(index)]
    command += ["-c:s", "srt"]
    for index, (_, language) in enumerate(tracks):
        command += [f"-metadata:s:s:{index}", f"language={language}"]
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
