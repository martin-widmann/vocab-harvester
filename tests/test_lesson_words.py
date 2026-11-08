from datetime import timedelta
from pathlib import Path

import pytest

from core import (
    FrequencyTable,
    VocabStore,
    WordState,
    build_frequency_table,
    new_words,
    pick_lesson_words,
    record_answer,
)

FIXTURES = Path(__file__).parent / "fixtures"
DARK = FIXTURES / "Dark"


@pytest.fixture
def store(tmp_path):
    return VocabStore(tmp_path / "vocab.sqlite")


@pytest.fixture
def frequency(tmp_path):
    path = tmp_path / "frequency.sqlite"
    with (FIXTURES / "frequency-sample.txt").open("rb") as source:
        build_frequency_table(source, path)
    return FrequencyTable(path)


def episode(folder: Path, lines: list[tuple[float, str]]) -> Path:
    """An Episode folder with one Line per (start minute, text)."""
    blocks = []
    for number, (minute, text) in enumerate(lines, start=1):
        start = timedelta(minutes=minute)
        blocks.append(f"{number}\n{_time(start)} --> {_time(start + timedelta(seconds=2))}\n{text}\n")
    folder.mkdir()
    (folder / "episode.srt").write_text("\n".join(blocks), encoding="utf-8")
    return folder


def _time(at: timedelta) -> str:
    seconds = int(at.total_seconds())
    return f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02},000"


def mark(store, folder, unknown: set[str]) -> None:
    """Do the Word Knowledge Check: the given Base forms Unknown, the rest Known."""
    for word in new_words(folder, store):
        record_answer(store, word, "U" if word.base_form in unknown else "K")


def base_forms(words):
    return [word.base_form for word in words]


def test_the_most_frequent_unknown_words_come_first_and_missing_words_last(
    store, frequency
):
    mark(store, DARK / "S01E01", {"aufgeben", "Höhle", "suchen", "Polizei", "wohnen"})

    picked = pick_lesson_words(DARK / "S01E01", store, frequency)

    # suchen 70, Polizei 50, wohnen 20; then Höhle and aufgeben, which the
    # table does not have, in the order they are first heard.
    assert base_forms(picked) == ["suchen", "Polizei", "wohnen", "Höhle", "aufgeben"]
    assert [word.count for word in picked] == [70, 50, 20, None, None]


def test_only_unknown_words_are_picked(store, frequency):
    mark(store, DARK / "S01E01", {"aufgeben", "Höhle"})
    store.add("warten", "VERB", WordState.TAUGHT)

    picked = pick_lesson_words(DARK / "S01E02", store, frequency)

    assert base_forms(picked) == ["Höhle", "aufgeben"]


NOUNS = [
    "Haus", "Baum", "Tisch", "Stuhl", "Fenster", "Auto", "Straße", "Stadt",
    "Brief", "Schule", "Lehrer", "Garten", "Blume", "Wasser", "Brot", "Kaffee",
    "Zimmer", "Tür", "Wand", "Lampe", "Bett", "Buch", "Uhr", "Hemd",
]


def test_at_most_20_unknown_words_are_picked_and_the_rest_stay_unknown(
    tmp_path, store, frequency
):
    folder = episode(
        tmp_path / "Long",
        [(minute, f"{noun}!") for minute, noun in enumerate(NOUNS)] + [(40, "Er sucht.")],
    )
    mark(store, folder, {*NOUNS, "suchen"})

    picked = pick_lesson_words(folder, store, frequency)

    assert len(picked) == 20
    assert base_forms(picked)[0] == "suchen"  # heard last, but the most frequent
    left = [noun for noun in NOUNS if noun not in base_forms(picked)]
    assert len(left) == 5
    assert all(store.state_of(noun) == WordState.UNKNOWN for noun in left)
    assert all(store.state_of(word.base_form) == WordState.UNKNOWN for word in picked)


def test_each_word_goes_to_the_section_of_the_first_line_it_is_heard_in(
    tmp_path, store, frequency
):
    folder = episode(
        tmp_path / "Sections",
        [
            (0, "Das Haus."),
            (14.9, "Der Baum."),
            (15, "Der Tisch."),
            (29.9, "Das Haus."),
            (30, "Der Stuhl."),
            (52, "Das Fenster."),
        ],
    )
    mark(store, folder, {"Haus", "Baum", "Tisch", "Stuhl", "Fenster"})

    picked = {word.base_form: word for word in pick_lesson_words(folder, store, frequency)}

    assert {form: word.section for form, word in picked.items()} == {
        "Haus": 1,
        "Baum": 1,
        "Tisch": 2,
        "Stuhl": 3,
        "Fenster": 3,
    }
    assert picked["Haus"].line.number == 1
    assert picked["Haus"].seen_form == "Haus"
