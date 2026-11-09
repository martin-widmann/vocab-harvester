from pathlib import Path

import pytest

from core import episode_key, find_episode

MEDIA = Path(__file__).parent / "fixtures"


def test_an_episode_is_found_from_its_name_under_the_media_root():
    assert find_episode(MEDIA, "Dark/S01E02") == (MEDIA / "Dark" / "S01E02").resolve()


def test_a_missing_episode_is_rejected():
    with pytest.raises(ValueError):
        find_episode(MEDIA, "Dark/S09E09")


def test_a_name_outside_the_media_root_is_rejected():
    with pytest.raises(ValueError):
        find_episode(MEDIA / "Dark", "../Dark/S01E01/../..")


@pytest.mark.parametrize("name", ["Dark/S01E02", "Dark/./S01E02", "Dark/S01E01/../S01E02"])
def test_an_episode_has_one_key_however_its_name_is_written(name):
    assert episode_key(MEDIA, name) == "Dark/S01E02"
