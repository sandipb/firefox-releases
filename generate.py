#!/usr/bin/env python3
"""Script to generate an RSS feed of Firefox releases."""
import argparse
import logging
import pathlib
from datetime import datetime

from jinja2 import Environment, FileSystemLoader

from firefox_releases import find_release_notes

THIS_DIR = pathlib.Path(__file__).parent


def get_parsed_args():
    """Parse the command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate an RSS feed and HTML page of Firefox releases."
    )

    parser.add_argument(
        "-o",
        "--output-dir",
        type=str,
        default=pathlib.Path(".").resolve(),
        help="The output directory (default: %(default)s).",
    )
    parser.add_argument(
        "-f",
        "--filename-prefix",
        type=str,
        default="index",
        help="The filename without extension (default: %(default)s).",
    )
    parser.add_argument(
        "-n",
        "--num_entries",
        type=int,
        default=20,
        help="The number of entries to include in the feed (default: %(default)s).",
    )
    parser.add_argument(
        "--skip-rss",
        action="store_true",
        help="Skip generating the RSS feed.",
    )
    parser.add_argument(
        "--skip-html",
        action="store_true",
        help="Skip generating the HTML page.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging."
    )
    # Parse the arguments
    return parser.parse_args()


def main(args: argparse.Namespace):
    """Generate the RSS feed and HTML page."""
    logging.basicConfig(
        # Enable logging in debug mode if the DEBUG environment variable is set, value doesnt matter
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logging.info("Generating RSS feed and HTML with %d entries", args.num_entries)
    logging.info("Loading templates")
    environment = Environment(loader=FileSystemLoader(THIS_DIR / "templates"))
    rss_template = environment.get_template("index.xml.j2")
    html_template = environment.get_template("index.html.j2")

    logging.info("Fetching release notes")
    releases = find_release_notes(
        max_num=args.num_entries, max_parse=int(1.5 * args.num_entries)
    )

    # Fill in the entries
    entries: list[dict] = []  # pylint: disable=invalid-name
    for release in releases:
        entry_time = datetime(
            release.date.year, release.date.month, release.date.day, 0, 0, 0
        )
        entries.append(
            {
                "name": release.name,
                "date": release.date.strftime("%B %d, %Y"),
                "time": entry_time.strftime("%a, %d %b %Y %H:%M:%S +0000"),
                "url": release.url,
            }
        )

    # Fill in the RSS boilerplate
    rss_file_name = pathlib.Path(args.output_dir) / f"{args.filename_prefix}.xml"
    rss_content = rss_template.render(releases=entries)
    html_file_name = pathlib.Path(args.output_dir) / f"{args.filename_prefix}.html"
    html_content = html_template.render(releases=entries, latest=entries[0])

    logging.info("Generating RSS feed to %s", rss_file_name)
    with open(rss_file_name, "w", encoding="utf-8") as f:
        f.write(rss_content)

    logging.info("Generating HTML content to %s", html_file_name)
    with open(html_file_name, "w", encoding="utf-8") as f:
        f.write(html_content)


if __name__ == "__main__":
    try:
        main(get_parsed_args())
    except KeyboardInterrupt:
        print("Interrupted by user")
