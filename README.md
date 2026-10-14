# firefox-releases

This code generates a list of latest firefox releases and provides a feed for the same.

- Website: <https://firefox-releases.foss-community.org/>
- Feed: <https://firefox-releases.foss-community.org/index.xml>
- JSON: <https://firefox-releases.foss-community.org/index.json>

## Running locally

Install Python, [uv](https://docs.astral.sh/uv/), and [Task](https://taskfile.dev/), then run `uv sync --locked`. Use `task test`, `task lint`, and `task generate` for the main project commands.

## Running the workflow locally

Install `act` and `gh`, sign in with `gh auth login`, then run `task act`.
