"""Exercise the API-to-site path without network requests."""

import json
from datetime import date
from pathlib import Path
from unittest.mock import Mock
from xml.etree import ElementTree

import pytest
import requests

import generate
from firefox_releases.releases import get_release_dates


@pytest.fixture
def api(monkeypatch):
    response = requests.Response()
    response.status_code = 200
    response._content = (
        Path(__file__).with_name("testdata").joinpath("wt_releases.json").read_bytes()
    )
    get = Mock(return_value=response)
    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr("firefox_releases.releases.time.sleep", Mock())
    clock = Mock(wraps=date)
    clock.today.return_value = date(2026, 10, 14)
    monkeypatch.setattr("firefox_releases.releases.date", clock)
    return get


def test_generate_downloaded_fixture(api, tmp_path):
    generate.main(generate.get_parsed_args(["-o", str(tmp_path), "-n", "2"]))

    data = json.loads((tmp_path / "index.json").read_text())
    assert [item["name"] for item in data] == ["158.0", "157.0.1"]
    assert data[0]["time"] == "Tue, 13 Oct 2026 00:00:00 +0000"

    items = ElementTree.parse(tmp_path / "index.xml").findall("./channel/item")
    assert [item.findtext("title") for item in items] == ["158.0", "157.0.1"]
    assert (
        items[0].findtext("link")
        == "https://www.mozilla.org/en-US/firefox/158.0/releasenotes/"
    )
    html = (tmp_path / "index.html").read_text()
    assert "158.0/releasenotes/" in html
    assert "157.0.1/releasenotes/" in html
    assert "157.0/releasenotes/" not in html


def test_filtering_and_numeric_order(api):
    api.return_value._content = b'{"125.2":"2024-03-19","125.10":"2024-03-19","123.0":"2024-02-20","999.0":"2099-01-01"}'

    releases = get_release_dates(oldest=date(2024, 3, 1))

    assert [release.name for release in releases] == ["125.10", "125.2"]


@pytest.mark.parametrize(
    "flag,extension", [("--skip-rss", "xml"), ("--skip-html", "html")]
)
def test_skip_output(api, tmp_path, flag, extension):
    generate.main(generate.get_parsed_args(["-o", str(tmp_path), flag]))

    assert not (tmp_path / f"index.{extension}").exists()
    assert (tmp_path / "index.json").exists()


def test_transient_failure_recovers(api, tmp_path):
    response = api.return_value
    failed = requests.Response()
    failed.status_code = 503
    api.side_effect = [failed, response]

    generate.main(generate.get_parsed_args(["-o", str(tmp_path)]))

    assert json.loads((tmp_path / "index.json").read_text())[0]["name"] == "158.0"
    assert api.call_count == 2


@pytest.mark.parametrize(
    "failure,attempts", [(requests.ConnectionError(), 3), (requests.HTTPError(), 1)]
)
def test_unavailable_feed_preserves_files(api, tmp_path, failure, attempts):
    api.side_effect = failure
    for extension in ("xml", "html", "json"):
        (tmp_path / f"index.{extension}").write_text("previous content")

    generate.main(generate.get_parsed_args(["-o", str(tmp_path)]))

    assert api.call_count == attempts
    assert all(path.read_text() == "previous content" for path in tmp_path.iterdir())
