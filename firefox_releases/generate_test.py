"""Behavior tests for the generated site and feed."""

import argparse
import json
from datetime import date
from xml.etree import ElementTree

import generate
from firefox_releases import Channel, Release


def args_for(output_dir, **overrides):
    values = {
        "output_dir": output_dir,
        "filename_prefix": "index",
        "num_entries": 2,
        "skip_rss": False,
        "skip_html": False,
        "verbose": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_generate_writes_matching_feed_site_and_json(mocker, tmp_path):
    releases = [
        Release(
            "125.0",
            (125, 0, 0),
            "https://example.test/125",
            date(2024, 3, 19),
            Channel.RELEASE,
        ),
        Release(
            "124.0",
            (124, 0, 0),
            "https://example.test/124",
            date(2024, 3, 5),
            Channel.RELEASE,
        ),
        Release(
            "123.0",
            (123, 0, 0),
            "https://example.test/123",
            date(2024, 2, 20),
            Channel.RELEASE,
        ),
    ]
    mocker.patch("generate.get_release_dates", return_value=releases)

    generate.main(args_for(tmp_path))

    data = json.loads((tmp_path / "index.json").read_text())
    assert [item["name"] for item in data] == ["125.0", "124.0"]
    assert data[0]["time"] == "Tue, 19 Mar 2024 00:00:00 +0000"

    feed = ElementTree.parse(tmp_path / "index.xml")
    assert [item.text for item in feed.findall("./channel/item/title")] == [
        "125.0",
        "124.0",
    ]
    assert [item.text for item in feed.findall("./channel/item/link")] == [
        "https://example.test/125",
        "https://example.test/124",
    ]

    html = (tmp_path / "index.html").read_text()
    assert "https://example.test/125" in html
    assert "https://example.test/124" in html
    assert "https://example.test/123" not in html


def test_generate_leaves_existing_files_when_api_has_no_data(mocker, tmp_path):
    mocker.patch("generate.get_release_dates", return_value=[])
    existing = tmp_path / "index.xml"
    existing.write_text("previous feed")

    generate.main(args_for(tmp_path))

    assert existing.read_text() == "previous feed"
    assert not (tmp_path / "index.html").exists()
    assert not (tmp_path / "index.json").exists()


def test_generate_respects_skip_flags(mocker, tmp_path):
    mocker.patch(
        "generate.get_release_dates",
        return_value=[
            Release(
                "125.0",
                (125, 0, 0),
                "https://example.test/125",
                date(2024, 3, 19),
                Channel.RELEASE,
            )
        ],
    )

    generate.main(args_for(tmp_path, skip_rss=True, skip_html=True))

    assert not (tmp_path / "index.xml").exists()
    assert not (tmp_path / "index.html").exists()
    assert json.loads((tmp_path / "index.json").read_text())[0]["name"] == "125.0"
