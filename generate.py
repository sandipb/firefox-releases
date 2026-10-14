#!/usr/bin/env python3
"""Script to generate an RSS feed of Firefox releases."""

import argparse
import json
import logging
import pathlib

from jinja2 import Environment, FileSystemLoader

from firefox_releases import get_release_dates

THIS_DIR = pathlib.Path(__file__).parent
logger = logging.getLogger(__name__)


def get_parsed_args(argv=None):
    """Parse the command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate an RSS feed and HTML page of Firefox releases."
    )

    parser.add_argument(
        "-o",
        "--output-dir",
        type=str,
        default=pathlib.Path.cwd(),
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
    return parser.parse_args(argv)


def main(args: argparse.Namespace):
    """Generate the RSS feed and HTML page."""
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.info("Generating RSS feed and HTML with %d entries", args.num_entries)
    logger.info("Fetching release notes")
    releases = get_release_dates()[: args.num_entries]
    if not releases:
        logger.warning("No release data available; leaving published files unchanged")
        return

    entries = [
        {
            "name": release.name,
            "date": release.date.strftime("%B %d, %Y"),
            "time": release.date.strftime("%a, %d %b %Y 00:00:00 +0000"),
            "url": release.url,
        }
        for release in releases
    ]
    environment = Environment(loader=FileSystemLoader(THIS_DIR / "templates"))
    output = pathlib.Path(args.output_dir) / args.filename_prefix
    for extension, skip in (("xml", args.skip_rss), ("html", args.skip_html)):
        if not skip:
            content = environment.get_template(f"index.{extension}.j2").render(
                releases=entries
            )
            pathlib.Path(f"{output}.{extension}").write_text(content, encoding="utf-8")
    pathlib.Path(f"{output}.json").write_text(json.dumps(entries), encoding="utf-8")


if __name__ == "__main__":
    try:
        main(get_parsed_args())
    except KeyboardInterrupt:
        print("Interrupted by user")
