# Repository guidance

- Use `uv` for Python dependencies and `Taskfile.yaml` for project commands. Keep `uv.lock` in sync with `pyproject.toml`.
- `firefox_releases/releases.py` fetches release data; `generate.py` renders the published files. Preserve existing published files when the upstream feed has no usable data.
- Add behavior tests for changes to parsing or output. Use fixtures or mocked HTTP; keep tests independent of the live feed and current release dates.
- Run `task all` before finishing. PR and publishing workflows must run tests.
