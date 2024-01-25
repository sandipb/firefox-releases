""" Find the release notes for the latest version of Firefox and print it as a list. """
import json
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# Fetch release notes for these many Firefox versions before sorting and limiting them
MAX_RELEASE_PARSE = 50

RELEASE_LIST_URL = "https://www.mozilla.org/en-US/firefox/releases/"
WT_API_RELEASES_URL = "https://whattrainisitnow.com/api/firefox/releases/"
WT_API_ESR_URL = "https://whattrainisitnow.com/api/esr/releases/"

logger = logging.getLogger(__name__)


class Channel(Enum):
    """Enum for the different Firefox channels."""

    RELEASE = "release"
    ESR = "esr"
    NIGHTLY = "nightly"
    BETA = "beta"


@dataclass
class Release:
    """Dataclass for a release."""

    name: str
    version: tuple[int, int, int]
    url: str
    date: date
    channel: Channel


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


def version_to_release_url(version: str) -> str:
    """Convert a version string to a release URL."""
    return f"https://www.mozilla.org/en-US/firefox/{version.strip()}/releasenotes/"


def get_release_dates(
    release_list_url=WT_API_RELEASES_URL,
    # esr_list_url=WT_API_ESR_URL,
    oldest=date.today().replace(date.today().year - 1),
) -> list[Release]:
    """Fetch the list of releases from the WT API and return the dates of the releases."""
    logger.debug("Fetching release list from %s", release_list_url)
    release_list: list[Release] = []
    try:
        releases_content = _fetch_url_content(release_list_url)
        # esr_content = _fetch_url_content(esr_list_url)
        release_data = json.loads(releases_content)
        # esr_data = json.loads(esr_content)
    except requests.exceptions.RequestException as e:
        logger.error("Error fetching release list: %s", e)
        return []
    except json.JSONDecodeError as e:
        logger.error("Error decoding release list: %s", e)
        return []
    logger.debug("Parsing release list")
    for release_name, release_date_str in release_data.items():
        release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
        if release_date < oldest:
            logger.debug(
                "Ignoring release %s with date %s, as it is older than cutoff by %s",
                release_name,
                release_date,
                oldest - release_date,
            )
            continue
        release_channel = Channel.RELEASE
        # if release_name in esr_data:
        #     release_channel = Channel.ESR
        release_url = version_to_release_url(release_name)
        release_list.append(
            Release(
                name=release_name,
                url=release_url,
                date=release_date,
                version=version_to_tuple(release_name),
                channel=release_channel,
            )
        )
    release_list.sort(
        key=lambda release: (
            release.date if release.date else date.min,
            release.version,
            release.channel,
        ),
        reverse=True,
    )
    return release_list


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
                        channel=Channel.RELEASE,
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
