# firefox-releases

Generates a website, RSS feed, and JSON list of Firefox releases from the [What Train Is It Now API](https://whattrainisitnow.com/api/firefox/releases/). Each entry links to Mozilla's release notes.

The scheduled GitHub Actions workflow publishes the latest 30 releases from the past year every three hours, ordered by release date and then numeric version. Future releases are excluded. Requests that fail transiently get up to three attempts; if no release data is available, publishing is skipped and the existing site stays online.

- [Website](https://firefox-releases.foss-community.org/)
- [RSS feed](https://firefox-releases.foss-community.org/index.xml)
- [JSON](https://firefox-releases.foss-community.org/index.json)

## Local commands

Install Python 3.13, [uv](https://docs.astral.sh/uv/), and [Task](https://taskfile.dev/).

```sh
uv sync --locked
task all       # Tests, lint, formatting checks, and pre-commit hooks
task generate  # Write public/index.html, index.xml, index.json, and CNAME
task serve     # Serve public/ locally
```

Tests use mocked HTTP responses and never contact the live API. PR and publishing workflows run tests. Dependabot checks Python dependencies, CI actions, and pre-commit hooks weekly.

Run `task fixtures:refresh` to download and validate the API fixture, then review the JSON diff. Its refresh task lives in `firefox_releases/testdata/Taskfile.yaml`. The generation test uses a fixed date so newer releases do not change its expected output.

To run the workflow locally, install `act` and `gh`, sign in with `gh auth login`, then run `task act`. To trigger publishing on GitHub, run `task deploy`.

## Discord and Mastodon announcements

The same three-hour workflow can announce the latest eligible release directly to Discord and `firefox_releases@mastodon.social`. The workflow fetches release data once, renders into a fresh output directory, publishes those files, then announces from that same RSS snapshot. It checks the public RSS up to 12 times, ten seconds apart, and sends only once it matches the snapshot. A fetch, rendering, publishing, or public-feed verification failure prevents announcements. Subsequent posting failures cannot block the completed website publication. Announcements stay disabled on scheduled runs until their repository variables are enabled; manual runs use the selected operation and target regardless of those variables.

Configure these GitHub Actions secrets:

| Secret | Purpose |
| --- | --- |
| `DISCORD_TEST_WEBHOOK` | Webhook for a separate test Discord channel |
| `DISCORD_WEBHOOK` | Webhook for the production Discord channel |
| `MASTODON_TOKEN` | User access token for the Mastodon account, with `write:statuses` permission |

The workflow uses its automatic `GITHUB_TOKEN` with repository contents write permission to persist delivery state. Webhook URLs and access tokens must stay in secrets.

### Test and activate

1. Add `DISCORD_TEST_WEBHOOK`, then explicitly replay the latest release to the test channel:

   ```sh
   gh workflow run generate-rss.yaml -f operation=test-replay -f target=discord-test
   ```

2. Verify the message text and release-notes link. Run `operation=run` against `target=discord-test` and confirm no duplicate appears. Set repository variable `ANNOUNCE_TEST` to `true` and observe scheduled delivery. Replays are restricted to test Discord; repeat the replay command only when another test post is needed.
3. Add production secrets. Disable the IFTTT applet, then baseline production at activation:

   ```sh
   gh workflow run generate-rss.yaml -f operation=baseline -f target=production
   ```

4. Wait for the baseline run to succeed, then set repository variable `ANNOUNCE_PRODUCTION` to `true`. Baseline records current releases without posting; subsequent runs announce newly observed releases. Disable `ANNOUNCE_TEST` when testing is complete.

There is a small handover gap between disabling IFTTT and baselining production. Compare the latest feed entry with the last IFTTT posts at cutover; manually announce any release missed during that gap.

To run production announcements manually after initialization:

```sh
gh workflow run generate-rss.yaml -f operation=run -f target=production
```

`task deploy` retains website-only publishing: the default manual target is `none`. For local announcement commands, supply a freshly generated feed whose publication has succeeded, and provide `GITHUB_REPOSITORY`, `GITHUB_TOKEN`, and the destination secrets in the environment. Do not run local state-changing commands concurrently with the workflow; workflow serialization cannot protect local invocations.

```sh
task announce -- --feed public/index.xml --published-url https://firefox-releases.foss-community.org/index.xml --destination discord-test --operation run
```

### State, retries, and recovery

Delivery state lives in `deliveries.json` on the `announcement-state` branch, separately for test Discord, production Discord, and Mastodon. Inspect that file and the Actions logs for delivery status, attempts, errors, retry timing, and returned post IDs. Each send records its intent first and saves its result immediately afterward. If saving fails, further sends stop. Missing initialization or corrupt state prevents normal posting; baseline refuses to reset an initialized destination.

Failed deliveries retry after fresh generation and successful publication on a subsequent three-hour run, respecting rate-limit retry timing. An unchanged latest release can still be retried; unavailable upstream data or a publishing failure postpones retries. Each destination proceeds independently when another fails. Only the latest eligible release is announced: when a newer release arrives, older pending or failed deliveries become superseded. Intermediate releases are not backfilled.

A request can succeed remotely before its result is saved, so retrying can produce a duplicate. Mastodon uses a stable idempotency key, but the server retains keys for only up to one hour, shorter than the scheduled retry interval. Discord webhook delivery has no equivalent duplicate protection.

For recovery, disable the affected scheduled destination variable, inspect state and remote posts, then repair the affected delivery record before re-enabling it. Preserve successful records and post IDs. Do not delete state or baseline again to clear failures: losing delivery history can cause duplicate announcements. Keep IFTTT disabled once production announcements are enabled.
