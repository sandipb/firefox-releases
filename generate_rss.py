"""Script to generate an RSS feed of Firefox releases."""
from datetime import datetime
import logging
import os
import sys
from firefox_releases import find_release_notes


# Define the RSS boilerplate
RSS_BOILERPLATE = """
<rss version="2.0">
  <channel>
    <title>Firefox Releases</title>
    <link>https://www.mozilla.org/en-US/firefox/releases/</link>
    <description>The latest Firefox releases</description>
    {entries}
  </channel>
</rss>
"""

# Define the entry boilerplate
ENTRY_BOILERPLATE = """
    <item>
        <title>{title}</title>
        <description>Firefox release {version} was released on {date}.</description>
        <link>{link}</link>
        <guid>{link}</guid>
        <pubDate>{datetime}</pubDate>
    </item>
"""

if __name__ == "__main__":
    output_path = "index.xml" if len(sys.argv) < 2 else sys.argv[1]

    logging.basicConfig(
        # Enable logging in debug mode if the DEBUG environment variable is set, value doesnt matter
        level=logging.INFO if "DEBUG" not in os.environ else logging.DEBUG,
        format="%(asctime)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    num_entries = 20 if "MAX_NUM" not in os.environ else int(os.environ["MAX_NUM"])  # pylint: disable=invalid-name
    logging.info("Generating RSS feed with %d entries", num_entries)
    releases = find_release_notes(max_num=num_entries, max_parse=int(1.5 * num_entries))

    # Fill in the entries
    entries = ""  # pylint: disable=invalid-name
    for release in releases:
        entry_time = datetime(
            release.date.year, release.date.month, release.date.day, 0, 0, 0
        )
        entries += ENTRY_BOILERPLATE.format(
            title=release.name,
            version=release.name,
            link=release.url,
            date=release.date.strftime("%B %d, %Y"),
            datetime=entry_time.strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

    # Fill in the RSS boilerplate
    rss_feed = RSS_BOILERPLATE.format(entries=entries)

    # Write the RSS feed to index.rss
    with open("index.rss", "w", encoding="utf-8") as f:
        f.write(rss_feed)
