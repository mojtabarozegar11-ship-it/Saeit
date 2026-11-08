"""Offline unit checks for the bounded official RSS reader."""

import unittest
from datetime import datetime, timezone

from core.news_feed_reader import MAX_FEED_BYTES, parse_official_rss


NOW = datetime(2026, 11, 8, 12, tzinfo=timezone.utc)


def rss(items):
    return ("<rss version='2.0'><channel>" + "".join(items) + "</channel></rss>").encode()


def item(link, date="Sun, 08 Nov 2026 10:00:00 GMT", title="Crop estimates"):
    return f"<item><title>{title}</title><link>{link}</link><pubDate>{date}</pubDate></item>"


class OfficialRssReaderTests(unittest.TestCase):
    def test_fresh_official_article_kept_and_http_normalized(self):
        rows = parse_official_rss(rss([item("http://www.nass.usda.gov/Newsroom/new")]), now=NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].url, "https://www.nass.usda.gov/Newsroom/new")

    def test_untrusted_hosts_credentials_and_scripts_rejected(self):
        rows = parse_official_rss(rss([
            item("https://www.nass.usda.gov.evil.example/news"),
            item("https://someone@www.nass.usda.gov/news"),
            item("javascript:alert(1)"),
        ]), now=NOW)
        self.assertEqual(rows, [])

    def test_duplicate_old_future_and_bad_dates_ignored(self):
        rows = parse_official_rss(rss([
            item("https://www.nass.usda.gov/new"),
            item("https://www.nass.usda.gov/new"),
            item("https://www.nass.usda.gov/old", date="Mon, 01 Jan 2024 00:00:00 GMT"),
            item("https://www.nass.usda.gov/future", date="Mon, 09 Nov 2026 10:00:00 GMT"),
            item("https://www.nass.usda.gov/bad", date="not-a-date"),
        ]), now=NOW)
        self.assertEqual(len(rows), 1)

    def test_invalid_and_excessive_xml_rejected(self):
        with self.assertRaises(ValueError):
            parse_official_rss(b"<html></html>", now=NOW)
        with self.assertRaises(ValueError):
            parse_official_rss(b"x" * (MAX_FEED_BYTES + 1), now=NOW)

    def test_bad_bounds_rejected(self):
        with self.assertRaises(ValueError):
            parse_official_rss(rss([]), now=NOW, max_items=0)


if __name__ == "__main__":
    unittest.main()
