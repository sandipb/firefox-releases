.PHONY: requirements check test generate serve

DOCS_URL:=firefox-releases.foss-community.org

requirements: requirements.txt

requirements.txt: pyproject.toml poetry.lock
	poetry export --format requirements.txt --output requirements.txt --without-hashes

test:
	poetry run pytest firefox_releases/

check:
	poetry run ruff check generate.py firefox_releases/

generate:
	mkdir -p public
	echo $(DOCS_URL) > public/CNAME
	poetry run python3 ./generate.py -o public -n 30

serve:
	poetry run python3 -m http.server --directory public
