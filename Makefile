.PHONY: requirements check test

requirements: requirements.txt

requirements.txt: pyproject.toml poetry.lock
	poetry export --format requirements.txt --output requirements.txt --without-hashes

test:
	poetry run pytest firefox_releases/

check:
	poetry run ruff check generate_rss.py firefox_releases/
