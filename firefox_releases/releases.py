"""Fetch and order released Firefox versions from What Train Is It Now."""

import json
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import requests

WT_API_RELEASES_URL = "https://whattrainisitnow.com/api/firefox/releases/"

logger = logging.getLogger(__name__)


@dataclass
class Release:
    """Dataclass for a release."""

    name: str
    url: str
    date: date


def _fetch_url_content(url: str) -> bytes:
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                time.sleep(2**attempt)
                continue
            response.raise_for_status()
            return response.content
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if attempt == 2:
                raise
            time.sleep(2**attempt)


def get_release_dates(
    release_list_url=WT_API_RELEASES_URL,
    oldest: date | None = None,
) -> list[Release]:
    """Fetch the list of releases from the WT API and return the dates of the releases."""
    logger.debug("Fetching release list from %s", release_list_url)
    today = date.today()
    if oldest is None:
        oldest = today - timedelta(days=365)
    release_list: list[Release] = []
    try:
        releases_content = _fetch_url_content(release_list_url)
        release_data = json.loads(releases_content)
    except requests.exceptions.RequestException as e:
        logger.error("Error fetching release list: %s", e)
        return []
    except json.JSONDecodeError as e:
        logger.error("Error decoding release list: %s", e)
        return []
    logger.debug("Parsing release list")
    for release_name, release_date_str in release_data.items():
        release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
        if not oldest <= release_date <= today:
            continue
        release_list.append(
            Release(
                name=release_name,
                url=f"https://www.mozilla.org/en-US/firefox/{release_name}/releasenotes/",
                date=release_date,
            )
        )
    release_list.sort(
        key=lambda release: (
            release.date,
            tuple(map(int, release.name.split("."))),
        ),
        reverse=True,
    )
    return release_list
