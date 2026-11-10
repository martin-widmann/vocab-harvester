import json
from pathlib import Path

import pytest

from core import episode_key, find_episode, match_episode

MEDIA = Path(__file__).parent / "fixtures"


def test_an_episode_is_found_from_its_name_under_the_media_root():
    assert find_episode(MEDIA, "Dark/S01E02").folder == (MEDIA / "Dark" / "S01E02").resolve()


def test_a_missing_episode_is_rejected():
    with pytest.raises(ValueError):
        find_episode(MEDIA, "Dark/S09E09")


def test_a_name_outside_the_media_root_is_rejected():
    with pytest.raises(ValueError):
        find_episode(MEDIA / "Dark", "../Dark/S01E01/../..")


@pytest.mark.parametrize("name", ["Dark/S01E02", "Dark/./S01E02", "Dark/S01E01/../S01E02"])
def test_an_episode_has_one_key_however_its_name_is_written(name):
    assert episode_key(MEDIA, name) == "Dark/S01E02"


@pytest.mark.parametrize(
    "request_text",
    ["Dark/S01E02", "Dark S01E02", "dark s01e02", "Dark s1e2", "  Dark   S01E02 "],
)
def test_an_episode_is_matched_from_how_the_learner_names_it(request_text):
    assert match_episode(MEDIA, request_text) == "Dark/S01E02"


def test_a_series_episode_folder_with_short_numbers_is_matched_too(tmp_path):
    (tmp_path / "Tatort" / "S1E3").mkdir(parents=True)

    assert match_episode(tmp_path, "Tatort S01E03") == "Tatort/S1E3"


def test_a_film_episode_is_matched_from_its_code(tmp_path):
    film = tmp_path / "Der Film"
    film.mkdir()
    (film / "film.json").write_text(
        json.dumps(
            {"P1": {"start": "0:00:00", "end": "0:50:00"}, "P2": {"start": "0:50:00", "end": None}}
        ),
        encoding="utf-8",
    )

    assert match_episode(tmp_path, "der film p2") == "Der Film/P2"
    assert match_episode(tmp_path, "Der Film/P1") == "Der Film/P1"
    with pytest.raises(ValueError, match="P1, P2"):
        match_episode(tmp_path, "Der Film")
    with pytest.raises(ValueError, match="P1, P2"):
        match_episode(tmp_path, "Der Film P3")


def test_an_unknown_series_names_the_series_in_the_media_folder():
    with pytest.raises(ValueError, match="No series or film 'Darkk'.*Dark"):
        match_episode(MEDIA, "Darkk S01E02")


def test_an_unknown_episode_names_the_episodes_of_the_series():
    with pytest.raises(ValueError, match="S01E01, S01E02"):
        match_episode(MEDIA, "Dark S09E09")


def test_a_series_without_an_episode_code_names_its_episodes():
    with pytest.raises(ValueError, match="S01E01, S01E02"):
        match_episode(MEDIA, "Dark")


@pytest.mark.parametrize("request_text", ["", "../..", "Dark/../.."])
def test_a_name_that_is_no_episode_is_rejected(request_text):
    with pytest.raises(ValueError):
        match_episode(MEDIA, request_text)


@pytest.mark.parametrize(
    "request_text", ["Dark - S01E02", "Dark, S01E02", "Dark_S01E02", "Dark S01E02."]
)
def test_punctuation_between_the_name_and_the_code_is_ignored(request_text):
    assert match_episode(MEDIA, request_text) == "Dark/S01E02"


def test_an_episode_folder_may_have_a_title_after_its_code(tmp_path):
    (tmp_path / "Tatort" / "S01E03 - Der Fall").mkdir(parents=True)

    assert match_episode(tmp_path, "Tatort S01E03") == "Tatort/S01E03 - Der Fall"


def test_two_folders_for_the_same_episode_are_rejected(tmp_path):
    (tmp_path / "Tatort" / "S01E03").mkdir(parents=True)
    (tmp_path / "Tatort" / "S1E3").mkdir()

    with pytest.raises(ValueError, match="more than one folder"):
        match_episode(tmp_path, "Tatort S01E03")
