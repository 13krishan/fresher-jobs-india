import pytest

from scraper.main import check_not_shrunk


def test_guard_blocks_big_drop():
    with pytest.raises(SystemExit):
        check_not_shrunk(published=100, previous=500)


def test_guard_allows_normal_change_and_first_runs():
    check_not_shrunk(published=480, previous=500)
    check_not_shrunk(published=10, previous=0)
    check_not_shrunk(published=5, previous=40)
