"""Offline unit checks for the bounded official RSS reader."""

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from core.news_feed_reader import (
    MAX_FEED_BYTES, OFFICIAL_FEEDS, fetch_official_news, parse_official_rss,
)


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

    def test_fao_newsroom_domain_and_iso_date_accepted(self):
        fao = OFFICIAL_FEEDS[1]
        raw = b"<rss><channel><item><title>Food security</title><link>https://www.fao.org/newsroom/detail/example/en</link><dc:date xmlns:dc='http://purl.org/dc/elements/1.1/'>2026-11-08T10:00:00Z</dc:date></item></channel></rss>"
        rows = parse_official_rss(raw, feed=fao, now=NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].publisher, fao.publisher)

    def test_one_feed_failure_retains_other_source(self):
        class Response:
            url = OFFICIAL_FEEDS[0].url

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def read(self, _):
                return rss([item("https://www.nass.usda.gov/new")])

        def fake_urlopen(request, timeout):
            if "fao.org" in request.full_url:
                raise TimeoutError("feed temporarily unavailable")
            return Response()

        with patch("core.news_feed_reader.urlopen", side_effect=fake_urlopen), patch(
            "core.news_feed_reader.datetime"
        ) as clock:
            clock.now.return_value = NOW
            report = fetch_official_news()
        self.assertEqual(report.feeds_ok, 1)
        self.assertEqual(len(report.items), 1)
        self.assertEqual(len(report.feed_errors), 1)


if __name__ == "__main__":
    unittest.main()
