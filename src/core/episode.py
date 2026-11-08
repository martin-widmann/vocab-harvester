"""Episode: find the New words of one Episode folder."""

from dataclasses import dataclass
from pathlib import Path

from core.subtitles import VIDEO_SUFFIXES, extract_subtitles, read_lines
from core.vocab_store import VocabStore
from core.word_analysis import analyse

DEFAULT_MEDIA_ROOT = Path(__file__).resolve().parents[2] / "media"


@dataclass(frozen=True)
class NewWord:
    """A Base form from an Episode that is not yet in the vocab store."""

    base_form: str
    word_type: str


def new_words(episode_folder: Path | str, store: VocabStore) -> list[NewWord]:
    """List the New words of an Episode, in the order they are first heard."""
    found: dict[str, NewWord] = {}
    for line in read_lines(subtitle_file(episode_folder)):
        for word in analyse(line.text):
            if word.base_form not in found and not store.contains(word.base_form):
                found[word.base_form] = NewWord(word.base_form, word.word_type)
    return list(found.values())


def find_episode(media_root: Path | str, name: str) -> Path:
    """The folder of an Episode from its name, for example "Dark/S01E03"."""
    root = Path(media_root).resolve()
    folder = (root / name).resolve()
    if not folder.is_relative_to(root) or not folder.is_dir():
        raise ValueError(f"No Episode {name!r} under {root}")
    return folder


def subtitle_file(episode_folder: Path | str) -> Path:
    """The original .srt of an Episode folder (not the tagged one).

    When the folder has no .srt but one video container, its German subtitle
    track is extracted to an .srt next to the video, once.
    """
    folder = Path(episode_folder)
    if not folder.is_dir():
        raise ValueError(f"No Episode folder {folder}")
    srts = [
        path for path in folder.glob("*.srt") if not path.name.endswith(".tagged.srt")
    ]
    if len(srts) == 1:
        return srts[0]
    if srts:
        raise ValueError(f"Expected one .srt file in {folder}, found {len(srts)}")
    videos = [
        path for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES
    ]
    if len(videos) != 1:
        raise ValueError(
            f"Expected one .srt file or one video in {folder}, "
            f"found no .srt and {len(videos)} videos"
        )
    return extract_subtitles(videos[0], videos[0].with_suffix(".srt"))
