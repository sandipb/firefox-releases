# Repository guidance

- Read `README.md` for project behavior, setup, and publishing commands.
- Apply YAGNI: choose the smallest complete solution, reuse existing code or standard-library features, and remove obsolete paths and unused dependencies. Add abstractions only for concrete needs.
- Use `uv` for Python dependencies and `Taskfile.yaml` for project commands. Keep `uv.lock` in sync with `pyproject.toml`.
- `firefox_releases/releases.py` fetches release data; `generate.py` renders the published files. Preserve existing published files when the upstream feed has no usable data.
- Keep tests proportionate to risk. Exercise observable behavior through real parsing, rendering, and file writes; mock HTTP and time. Avoid assertions that merely repeat implementation.
- Use committed API fixtures and a fixed clock. Refresh with `task fixtures:refresh` and review the JSON diff. Keep synthetic cases for edge conditions missing from the downloaded data; CI tests must run offline.
- Verify full action release tags exist before updating CI; major-version aliases may be absent.
- Run `task all` before finishing. PR and publishing workflows must run tests.
