"""Deliver release announcements with durable, per-destination GitHub state."""

import argparse
import base64
import hashlib
import json
import logging
import os
import time
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

from firefox_releases.releases import get_release_dates

logger = logging.getLogger(__name__)
DESTINATIONS = ("discord-test", "discord", "mastodon")
STATUSES = {"delivered", "baselined", "failed", "pending", "superseded"}


class StateError(Exception):
    """State cannot safely be read or persisted."""


class GitHubState:
    """Keep a local inspection copy of state persisted through GitHub's API."""

    def __init__(self, path):
        self.path = Path(path)
        self.branch = "announcement-state"
        self.url = f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}"
        self.headers = {
            "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self.sha = None

    def request(self, method, endpoint, **kwargs):
        try:
            return requests.request(
                method, self.url + endpoint, headers=self.headers, timeout=30, **kwargs
            )
        except requests.RequestException:
            raise StateError("GitHub state request failed") from None

    def load(self):
        result = self.request(
            "GET", "/contents/deliveries.json", params={"ref": self.branch}
        )
        if result.status_code == 404:
            return {"schema": 1, "destinations": {}}
        if result.status_code != 200:
            raise StateError(f"GitHub state read HTTP {result.status_code}")
        try:
            envelope = result.json()
            self.sha = envelope["sha"]
            self.path.write_bytes(base64.b64decode(envelope["content"], validate=False))
            state = json.loads(self.path.read_text())
            if state["schema"] != 1 or not isinstance(state["destinations"], dict):
                raise ValueError
            for destination, deliveries in state["destinations"].items():
                if destination not in DESTINATIONS or not isinstance(deliveries, dict):
                    raise ValueError
                for version, record in deliveries.items():
                    if not isinstance(version, str) or record["status"] not in STATUSES:
                        raise ValueError
                    if type(record["attempts"]) is not int or record["attempts"] < 0:
                        raise ValueError
                    if not isinstance(record.get("retry_at", 0), (int, float)):
                        raise TypeError
            return state
        except (ValueError, KeyError, TypeError, OSError):
            raise StateError(
                "Invalid announcement state; repair before posting"
            ) from None

    def save(self, state):
        if self.sha is None:
            branch = self.request("GET", f"/git/ref/heads/{self.branch}")
            if branch.status_code == 404:
                head = self.request("GET", "/commits/HEAD")
                if head.status_code != 200:
                    raise StateError("Cannot find repository HEAD")
                branch = self.request(
                    "POST",
                    "/git/refs",
                    json={
                        "ref": f"refs/heads/{self.branch}",
                        "sha": head.json()["sha"],
                    },
                )
            if branch.status_code not in (200, 201):
                raise StateError("Cannot create or read announcement state branch")
        try:
            self.path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
            body = {
                "message": "Update announcement delivery state",
                "branch": self.branch,
                "content": base64.b64encode(self.path.read_bytes()).decode(),
            }
            if self.sha is not None:
                body["sha"] = self.sha
            result = self.request("PUT", "/contents/deliveries.json", json=body)
            if result.status_code not in (200, 201):
                raise StateError(f"GitHub state save HTTP {result.status_code}")
            self.sha = result.json()["content"]["sha"]
        except (OSError, KeyError, ValueError, TypeError):
            raise StateError("Cannot persist announcement state") from None


def send(destination, release):
    description = (
        f"Firefox release {release.name} was released on "
        f"{release.date.strftime('%B %d, %Y')}."
    )
    if destination.startswith("discord"):
        key = (
            "DISCORD_TEST_WEBHOOK"
            if destination == "discord-test"
            else "DISCORD_WEBHOOK"
        )
        return requests.post(
            os.environ[key],
            params={"wait": "true"},
            json={
                "content": f"{description}\nRelease notes at: {release.url}",
                "allowed_mentions": {"parse": []},
            },
            timeout=30,
        )
    identity = hashlib.sha256(f"{destination}:{release.name}".encode()).hexdigest()
    return requests.post(
        "https://mastodon.social/api/v1/statuses",
        headers={
            "Authorization": f"Bearer {os.environ['MASTODON_TOKEN']}",
            "Idempotency-Key": identity,
        },
        json={
            "status": f"{description}. Release notes at {release.url}.",
            "visibility": "public",
        },
        timeout=30,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--destination", action="append", choices=DESTINATIONS, required=True
    )
    parser.add_argument(
        "--operation", choices=("run", "baseline", "test-replay"), default="run"
    )
    parser.add_argument("--state-file", default="announcement-state.json")
    args = parser.parse_args(argv)
    destinations = list(dict.fromkeys(args.destination))
    try:
        if args.operation == "test-replay" and destinations != ["discord-test"]:
            raise StateError("Replay is restricted to test Discord")
        store = GitHubState(args.state_file)
        state = store.load()
        if args.operation == "run" and any(
            d not in state["destinations"] for d in destinations
        ):
            raise StateError(
                "Destination not initialized; explicitly baseline or test-replay"
            )
        if args.operation == "baseline" and any(
            d in state["destinations"] for d in destinations
        ):
            raise StateError("Destination already initialized; refusing to reset state")
        releases = get_release_dates()
        if not releases:
            logger.error("No usable release data; state unchanged")
            return 1
        latest = releases[0]
        if args.operation == "baseline":
            for destination in destinations:
                state["destinations"][destination] = {
                    release.name: {"status": "baselined", "attempts": 0}
                    for release in releases
                }
            store.save(state)
            return 0
        failed = False
        for destination in destinations:
            records = state["destinations"].setdefault(destination, {})
            if args.operation == "test-replay":
                records.pop(latest.name, None)
            for version, record in records.items():
                if version != latest.name and record["status"] in {"pending", "failed"}:
                    record["status"] = "superseded"
            record = records.setdefault(
                latest.name, {"status": "pending", "attempts": 0}
            )
            if record["status"] in {"delivered", "baselined", "superseded"}:
                continue
            if record.get("retry_at", 0) > time.time():
                failed = True
                store.save(state)
                continue
            # Persist intent before posting; a state outage must not cause new sends.
            record["attempts"] += 1
            record["status"] = "pending"
            record.pop("last_error", None)
            store.save(state)
            try:
                result = send(destination, latest)
                if not 200 <= result.status_code < 300:
                    record["last_error"] = f"HTTP {result.status_code}"
                    if result.status_code == 429:
                        retry_after = result.headers.get("Retry-After")
                        try:
                            if retry_after:
                                try:
                                    delay = float(retry_after)
                                except ValueError:
                                    delay = (
                                        parsedate_to_datetime(retry_after).timestamp()
                                        - time.time()
                                    )
                            else:
                                delay = float(result.json().get("retry_after", 10800))
                        except (ValueError, TypeError):
                            delay = 10800
                        record["retry_at"] = time.time() + max(0, delay)
                    raise requests.HTTPError
                post_id = result.json()["id"]
                if not isinstance(post_id, str) or not post_id:
                    raise ValueError
                record.update(status="delivered", post_id=post_id)
                record.pop("last_error", None)
                record.pop("retry_at", None)
            except (requests.RequestException, ValueError, KeyError, TypeError):
                record["status"] = "failed"
                record.setdefault("last_error", "Posting failed or outcome uncertain")
                logger.error(
                    "%s delivery failed: %s", destination, record["last_error"]
                )
                failed = True
            store.save(state)
        return int(failed)
    except StateError as error:
        logger.error("%s; stopping further sends", error)
        return 1
    except (KeyError, ValueError, TypeError, OSError):
        logger.error("Announcement state/configuration failure; stopping further sends")
        return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
