"""Exercise announcements through the command with HTTP boundaries mocked."""

import json
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

import generate
from firefox_releases import announcements


def response(data, status=200):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(data).encode()
    return result


@pytest.fixture
def delivery(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_TOKEN", "github-secret")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv(
        "DISCORD_TEST_WEBHOOK", "https://discord.com/api/webhooks/test/secret"
    )
    monkeypatch.setenv(
        "DISCORD_WEBHOOK", "https://discord.com/api/webhooks/live/secret"
    )
    monkeypatch.setenv("MASTODON_TOKEN", "mastodon-secret")
    clock = Mock(wraps=date)
    clock.today.return_value = date(2026, 10, 14)
    monkeypatch.setattr("firefox_releases.releases.date", clock)
    source = Mock(
        return_value=response(
            json.loads(
                Path(__file__)
                .with_name("testdata")
                .joinpath("wt_releases.json")
                .read_text()
            )
        )
    )
    monkeypatch.setattr(requests, "get", source)
    monkeypatch.setattr("firefox_releases.releases.time.sleep", Mock())
    remote = {}

    def github(method, url, **kwargs):
        if "/contents/" not in url:
            return response({"object": {"sha": "head"}})
        if method == "GET":
            return response(remote, 200 if remote else 404)
        import base64

        remote.update({"sha": "saved", "content": kwargs["json"]["content"]})
        # Decode each remote write: persistence must always be valid JSON.
        json.loads(base64.b64decode(remote["content"]))
        return response({"content": {"sha": "saved"}})

    storage = Mock(side_effect=github)
    monkeypatch.setattr(requests, "request", storage)
    post = Mock(return_value=response({"id": "post-1"}))
    monkeypatch.setattr(requests, "post", post)

    snapshots = 0

    def run(*args):
        nonlocal snapshots
        snapshots += 1
        output = tmp_path / f"snapshot-{snapshots}"
        output.mkdir()
        generate.main(generate.get_parsed_args(["-o", str(output)]))
        return announcements.main(
            [
                "--feed",
                str(output / "index.xml"),
                "--state-file",
                str(tmp_path / "state.json"),
                *args,
            ]
        )

    return run, post, source, storage, remote, tmp_path / "state.json"


def test_trial_replay_persists_and_does_not_repeat(delivery):
    run, post, _, _, _, state = delivery
    assert run("--destination", "discord-test", "--operation", "test-replay") == 0
    assert post.call_args.kwargs["json"] == {
        "content": "Firefox release 158.0 was released on October 13, 2026.\nRelease notes at: https://www.mozilla.org/en-US/firefox/158.0/releasenotes/",
        "allowed_mentions": {"parse": []},
    }
    assert (
        json.loads(state.read_text())["destinations"]["discord-test"]["158.0"]["status"]
        == "delivered"
    )
    assert run("--destination", "discord-test") == 0
    assert post.call_count == 1


def test_production_baseline_is_silent_and_isolated_from_trial(delivery):
    run, post, source, _, _, _ = delivery
    assert run("--destination", "discord-test", "--operation", "test-replay") == 0
    assert run("--destination", "discord") == 1
    assert (
        run(
            "--destination",
            "discord",
            "--destination",
            "mastodon",
            "--operation",
            "baseline",
        )
        == 0
    )
    assert run("--destination", "discord", "--destination", "mastodon") == 0
    assert post.call_count == 1
    assert run("--destination", "discord", "--operation", "baseline") == 1
    source.return_value = response({"159.0": "2026-10-14"})
    assert run("--destination", "discord", "--destination", "mastodon") == 0
    assert post.call_count == 3
    assert post.call_args.kwargs["json"] == {
        "status": "Firefox release 159.0 was released on October 14, 2026.. Release notes at https://www.mozilla.org/en-US/firefox/159.0/releasenotes/.",
        "visibility": "public",
    }
    assert post.call_args.kwargs["headers"]["Idempotency-Key"]


def test_failed_destination_retries_without_repeating_success(delivery, caplog):
    run, post, source, _, _, state = delivery
    assert (
        run(
            "--destination",
            "discord",
            "--destination",
            "mastodon",
            "--operation",
            "baseline",
        )
        == 0
    )
    source.return_value = response({"159.0": "2026-10-14"})
    post.side_effect = [
        requests.Timeout("https://secret.example/token"),
        response({"id": "m1"}),
        response({"id": "d1"}),
    ]
    assert run("--destination", "discord", "--destination", "mastodon") == 1
    assert "secret.example" not in caplog.text + state.read_text()
    assert run("--destination", "discord", "--destination", "mastodon") == 0
    assert post.call_count == 3
    assert (
        json.loads(state.read_text())["destinations"]["discord"]["159.0"]["attempts"]
        == 2
    )


def test_new_latest_supersedes_failed_delivery(delivery):
    run, post, source, _, _, state = delivery
    post.return_value = response({}, 503)
    assert run("--destination", "discord-test", "--operation", "test-replay") == 1
    source.return_value = response({"159.0": "2026-10-14", "158.1": "2026-10-14"})
    post.return_value = response({"id": "new"})
    assert run("--destination", "discord-test") == 0
    assert "159.0" in post.call_args.kwargs["json"]["content"]
    assert (
        json.loads(state.read_text())["destinations"]["discord-test"]["158.0"]["status"]
        == "superseded"
    )


def test_remote_save_failure_after_post_stops_other_destination(delivery):
    run, post, source, storage, _, _ = delivery
    assert (
        run(
            "--destination",
            "discord",
            "--destination",
            "mastodon",
            "--operation",
            "baseline",
        )
        == 0
    )
    source.return_value = response({"159.0": "2026-10-14"})
    normal = storage.side_effect
    writes = 0

    def fail_after_intent(method, url, **kwargs):
        nonlocal writes
        if method == "PUT":
            writes += 1
            if writes == 2:
                return response({}, 503)
        return normal(method, url, **kwargs)

    storage.side_effect = fail_after_intent
    assert run("--destination", "discord", "--destination", "mastodon") == 1
    assert post.call_count == 1


@pytest.mark.parametrize(
    "content",
    [None, "not-json", '{"schema": 1, "destinations": {"discord-test": {"1": {}}}}'],
)
def test_missing_or_corrupt_state_stops_posting(delivery, content):
    import base64

    run, post, _, _, remote, _ = delivery
    if content is not None:
        remote.update(sha="bad", content=base64.b64encode(content.encode()).decode())
    assert run("--destination", "discord-test") == 1
    post.assert_not_called()


def test_unavailable_source_does_not_reset_state(delivery):
    run, post, source, _, remote, _ = delivery
    assert run("--destination", "discord-test", "--operation", "test-replay") == 0
    previous = remote.copy()
    source.return_value = response({})
    assert run("--destination", "discord-test") == 1
    assert remote == previous
    assert post.call_count == 1


def test_rate_limit_defers_retry_even_on_manual_run(delivery, monkeypatch):
    run, post, _, _, _, _ = delivery
    monkeypatch.setattr("firefox_releases.announcements.time.time", lambda: 1000)
    post.return_value = response({"retry_after": 20000}, 429)
    assert run("--destination", "discord-test", "--operation", "test-replay") == 1
    assert run("--destination", "discord-test") == 1
    assert post.call_count == 1
    monkeypatch.setattr("firefox_releases.announcements.time.time", lambda: 22000)
    post.return_value = response({"id": "retry"})
    assert run("--destination", "discord-test") == 0
    assert post.call_count == 2


def test_replay_cannot_target_production(delivery):
    run, post, _, _, _, _ = delivery
    assert run("--destination", "mastodon", "--operation", "test-replay") == 1
    post.assert_not_called()


def test_http_date_rate_limit_is_honored(delivery, monkeypatch):
    run, post, _, _, _, _ = delivery
    monkeypatch.setattr("firefox_releases.announcements.time.time", lambda: 0)
    limited = response({}, 429)
    limited.headers["Retry-After"] = "Fri, 02 Jan 1970 00:00:00 GMT"
    post.return_value = limited
    assert run("--destination", "discord-test", "--operation", "test-replay") == 1
    monkeypatch.setattr("firefox_releases.announcements.time.time", lambda: 20000)
    assert run("--destination", "discord-test") == 1
    assert post.call_count == 1


def test_initialization_creates_missing_state_branch_before_posting(delivery):
    run, post, _, storage, _, _ = delivery
    normal = storage.side_effect
    operations = []

    def missing_branch(method, url, **kwargs):
        operations.append((method, url, kwargs.get("json")))
        if url.endswith("/git/ref/heads/announcement-state"):
            return response({}, 404)
        if url.endswith("/commits/HEAD"):
            return response({"sha": "initial-head"})
        if url.endswith("/git/refs"):
            return response({}, 201)
        return normal(method, url, **kwargs)

    storage.side_effect = missing_branch
    assert run("--destination", "discord-test", "--operation", "test-replay") == 0
    assert any(
        body == {"ref": "refs/heads/announcement-state", "sha": "initial-head"}
        for _, _, body in operations
    )
    assert post.call_count == 1


def test_last_error_describes_most_recent_failure(delivery):
    run, post, _, _, _, state = delivery
    post.return_value = response({}, 503)
    assert run("--destination", "discord-test", "--operation", "test-replay") == 1
    post.side_effect = requests.Timeout("secret")
    assert run("--destination", "discord-test") == 1
    record = json.loads(state.read_text())["destinations"]["discord-test"]["158.0"]
    assert record["last_error"] == "Posting failed or outcome uncertain"


def test_announcements_use_rendered_rss_without_refetching(delivery, tmp_path):
    import generate

    _, post, source, _, _, _ = delivery
    generate.main(generate.get_parsed_args(["-o", str(tmp_path)]))
    assert source.call_count == 1
    # Upstream now has another release; announcements must use the saved RSS.
    source.return_value = response({"159.0": "2026-10-14"})
    assert (
        announcements.main(
            [
                "--feed",
                str(tmp_path / "index.xml"),
                "--state-file",
                str(tmp_path / "state.json"),
                "--destination",
                "discord-test",
                "--operation",
                "test-replay",
            ]
        )
        == 0
    )
    assert source.call_count == 1
    assert "Firefox release 158.0" in post.call_args.kwargs["json"]["content"]


@pytest.mark.parametrize("content", [None, "broken XML", "<rss><channel/></rss>"])
def test_unusable_snapshot_does_not_fetch_or_change_delivery_state(
    delivery, tmp_path, content
):
    _, post, source, storage, _, _ = delivery
    feed = tmp_path / "missing.xml"
    if content is not None:
        feed.write_text(content)
    assert (
        announcements.main(
            [
                "--feed",
                str(feed),
                "--destination",
                "discord-test",
                "--operation",
                "test-replay",
            ]
        )
        == 1
    )
    source.assert_not_called()
    storage.assert_not_called()
    post.assert_not_called()


def test_stale_public_rss_prevents_delivery(delivery, tmp_path, monkeypatch):
    _, post, source, storage, _, _ = delivery
    generate.main(generate.get_parsed_args(["-o", str(tmp_path)]))
    source.return_value = response({})
    monkeypatch.setattr("firefox_releases.announcements.time.sleep", Mock())
    assert (
        announcements.main(
            [
                "--feed",
                str(tmp_path / "index.xml"),
                "--published-url",
                "https://feed.example/index.xml",
                "--destination",
                "discord-test",
                "--operation",
                "test-replay",
            ]
        )
        == 1
    )
    storage.assert_not_called()
    post.assert_not_called()


def test_delivery_waits_for_public_rss_to_match(delivery, tmp_path, monkeypatch):
    _, post, source, _, _, _ = delivery
    generate.main(generate.get_parsed_args(["-o", str(tmp_path)]))
    fresh = requests.Response()
    fresh.status_code = 200
    fresh._content = (tmp_path / "index.xml").read_bytes()
    source.side_effect = [requests.Timeout(), response({}), fresh]
    monkeypatch.setattr("firefox_releases.announcements.time.sleep", Mock())
    assert (
        announcements.main(
            [
                "--feed",
                str(tmp_path / "index.xml"),
                "--published-url",
                "https://feed.example/index.xml",
                "--state-file",
                str(tmp_path / "state.json"),
                "--destination",
                "discord-test",
                "--operation",
                "test-replay",
            ]
        )
        == 0
    )
    assert post.call_count == 1
    assert source.call_args.args == ("https://feed.example/index.xml",)
