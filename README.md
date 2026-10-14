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

To run the workflow locally, install `act` and `gh`, sign in with `gh auth login`, then run `task act`. To trigger publishing on GitHub, run `task deploy`.
