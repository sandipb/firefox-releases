""" Find the release notes for the latest version of Firefox and print it as a list. """
from dataclasses import dataclass
from datetime import date, datetime
import os
import logging
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# Fetch release notes for these many Firefox versions before sorting and limiting them
MAX_RELEASE_PARSE = 50

RELEASE_LIST_URL = "https://www.mozilla.org/en-US/firefox/releases/"

logger = logging.getLogger(__name__)


@dataclass
class Release:
    """Dataclass for a release."""

    name: str
    version: tuple[int, int, int]
    url: str
    date: date


def version_to_tuple(version: str) -> tuple[int, int, int]:
    """Convert a version string to a tuple."""
    version_list = list(map(int, version.split(".")))
    if len(version_list) < 3:
        version_list += [0] * (3 - len(version_list))
    return tuple(version_list[:3])


def find_release_date(release_url: str) -> datetime | None:
    """Find the release date of a Firefox version."""
    release_date: datetime | None = None
    logger.debug("Fetching release date from %s", release_url)
    try:
        content = _fetch_url_content(release_url)
        soup = BeautifulSoup(content, "html.parser")
        date_content = soup.find("p", {"class": "c-release-date"})
        if date_content:
            release_date = datetime.strptime(date_content.text, "%B %d, %Y").date()
    except requests.exceptions.RequestException as e:
        logger.error("Error fetching release date: %s", e)

    return release_date


def _fetch_url_content(url: str) -> str:
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    return response.content


def find_release_notes(
    release_list_url: str = RELEASE_LIST_URL,
    max_num: int = 30,
    max_parse: int = MAX_RELEASE_PARSE,
) -> list[Release]:
    """Find the release notes for the latest version of Firefox and print it as a list."""
    logger.debug("Fetching release list from %s", release_list_url)
    try:
        content = _fetch_url_content(release_list_url)
    except requests.exceptions.RequestException as e:
        logger.error("Error fetching release list: %s", e)
        return []
    logger.debug("Parsing release list")
    soup = BeautifulSoup(content, "html.parser")
    main_content = soup.find("main", {"id": "main-content"})

    result: list[Release] = []
    if main_content:
        count = 0
        for a_tag in main_content.find_all("a", href=True):  # type: ignore
            if "releasenotes" in a_tag["href"]:
                if count >= max_parse:
                    break
                absolute_url = urljoin(release_list_url, a_tag["href"])
                release_date = find_release_date(absolute_url)
                result.append(
                    Release(
                        name=a_tag.text.strip(),
                        url=absolute_url,
                        date=release_date,
                        version=version_to_tuple(a_tag.text.strip()),
                    )
                )
                count += 1
        result.sort(
            key=lambda release: (
                release.date if release.date else date.min,
                release.version,
            ),
            reverse=True,
        )
    return result[:max_num]


# def gen_rss_feed(releases) -> str:
#     """Generate an RSS feed from the release notes."""
#     releases = find_release_notes(url)
#     rss_feed = """<?xml version="1.0" encoding="UTF-8"?>"""

if __name__ == "__main__":
    logging.basicConfig(
        # Enable logging in debug mode if the DEBUG environment variable is set, value doesnt matter
        level=logging.INFO if "DEBUG" not in os.environ else logging.DEBUG,
        format="%(asctime)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    releases = find_release_notes(
        RELEASE_LIST_URL,
        20 if "RELEASE_MAX" not in os.environ else int(os.environ["RELEASE_MAX"]),
    )
    for i, release in enumerate(releases):
        print(f"{i+1}: {release.name} - {release.date} - {release.url}")
