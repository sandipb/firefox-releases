# pylint: disable=C0114
import pathlib
from datetime import date

import pytest
import requests

from firefox_releases.releases import (
    RELEASE_LIST_URL,
    _fetch_url_content,
    find_release_date,
    find_release_notes,
    get_release_dates,
    version_to_tuple,
)


@pytest.fixture
def release_list_content():
    """Return the content of the release list page."""
    with (
        pathlib.Path(__file__)
        .parent.joinpath("testdata", "firefox_releases.html")
        .open(encoding="utf-8") as f
    ):
        return f.read()


@pytest.fixture
def release_content():
    """Return the content of the release list page."""
    with (
        pathlib.Path(__file__)
        .parent.joinpath("testdata", "122_0.html")
        .open(encoding="utf-8") as f
    ):
        return f.read()


@pytest.fixture
def wt_releases_content():
    """Return the content of the release list page."""
    with (
        pathlib.Path(__file__)
        .parent.joinpath("testdata", "wt_releases.json")
        .open(encoding="utf-8") as f
    ):
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


def test_get_release_dates(mocker, wt_releases_content):  # pylint: disable=redefined-outer-name
    """Test find_release_notes()."""

    mocker.patch(
        "firefox_releases.releases._fetch_url_content",
        return_value=wt_releases_content,
    )
    releases = get_release_dates(oldest=date(2024, 1, 1))
    assert releases[0].name == "122.0"
    assert (
        releases[0].url == "https://www.mozilla.org/en-US/firefox/122.0/releasenotes/"
    )
    assert releases[0].date == date(2024, 1, 23)
    assert releases[0].version == (122, 0, 0)


def test_get_release_dates_excludes_old_and_future_releases(mocker):
    mocker.patch(
        "firefox_releases.releases._fetch_url_content",
        return_value='{"123.0":"2024-02-01","124.0":"2024-03-01","999.0":"2099-01-01"}',
    )

    releases = get_release_dates(oldest=date(2024, 3, 1))

    assert [release.name for release in releases] == ["124.0"]


def test_fetch_url_content_retries_server_error(mocker):
    first = mocker.Mock(status_code=500)
    second = mocker.Mock(status_code=200, content=b"release data")
    get = mocker.patch(
        "firefox_releases.releases.requests.get", side_effect=[first, second]
    )
    sleep = mocker.patch("firefox_releases.releases.time.sleep")

    assert _fetch_url_content("https://example.test/releases") == b"release data"
    assert get.call_count == 2
    sleep.assert_called_once_with(1)


def test_fetch_url_content_does_not_retry_client_error(mocker):
    response = mocker.Mock(status_code=404)
    response.raise_for_status.side_effect = requests.HTTPError("not found")
    get = mocker.patch("firefox_releases.releases.requests.get", return_value=response)
    sleep = mocker.patch("firefox_releases.releases.time.sleep")

    with pytest.raises(requests.HTTPError):
        _fetch_url_content("https://example.test/missing")

    get.assert_called_once()
    sleep.assert_not_called()
