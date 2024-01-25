from datetime import date
import pathlib

import pytest

from firefox_releases.releases import (
    find_release_date,
    find_release_notes,
    version_to_tuple,
    RELEASE_LIST_URL,
)


@pytest.fixture
def release_list_content():
    """Return the content of the release list page."""
    with pathlib.Path(__file__).parent.joinpath(
        "testdata", "firefox_releases.html"
    ).open(encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def release_content():
    """Return the content of the release list page."""
    with pathlib.Path(__file__).parent.joinpath("testdata", "122_0.html").open(
        encoding="utf-8"
    ) as f:
        return f.read()


def test_version_to_tuple():
    """Test different possible firefox version specifiers."""
    assert version_to_tuple("1.2.3") == (1, 2, 3)
    assert version_to_tuple("1.2") == (1, 2, 0)
    assert version_to_tuple("1") == (1, 0, 0)
    assert version_to_tuple("1.2.3.4") == (1, 2, 3)


def test_find_release_notes(mocker, release_list_content, release_content):  # pylint: disable=redefined-outer-name
    """Test find_release_notes()."""

    def mock_fetch_url_content(url):
        if url == RELEASE_LIST_URL:
            return release_list_content
        else:
            return release_content  # return the same for all releases

    mocker.patch(
        "firefox_releases.releases._fetch_url_content",
        side_effect=mock_fetch_url_content,
    )
    releases = find_release_notes(max_num=3)
    assert len(releases) == 3
    assert releases[0].name == "122.0"
    assert (
        releases[0].url == "https://www.mozilla.org/en-US/firefox/122.0/releasenotes/"
    )
    assert releases[0].date == date(2024, 1, 23)
    assert releases[0].version == (122, 0, 0)


def test_find_release_date(mocker, release_content):  # pylint: disable=redefined-outer-name
    """Test parsing release note for a specific version"""

    mocker.patch(
        "firefox_releases.releases._fetch_url_content",
        return_value=release_content,
    )
    release_date = find_release_date(
        "https://www.mozilla.org/en-US/firefox/122.0/releasenotes/"
    )
    assert release_date == date(2024, 1, 23)
