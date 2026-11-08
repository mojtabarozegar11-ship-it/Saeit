"""Offline unit checks for the bounded official RSS reader."""

import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from urllib.request import Request

from core.news_feed_reader import (
    MAX_FEED_BYTES, OFFICIAL_FEEDS, _OfficialRedirectsOnly, editorial_identity,
    fetch_official_news, parse_official_rss,
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

    def test_political_and_israel_news_are_discarded_before_draft_creation(self):
        raw = rss([
            item("https://www.nass.usda.gov/news/israel/crops", title="Crop estimates"),
            item("https://www.nass.usda.gov/news/minister", title="Minister announces crops"),
            "<item><title>Crop report</title><link>https://www.nass.usda.gov/news/brief</link>"
            "<description>Parliament vote</description><pubDate>Sun, 08 Nov 2026 10:00:00 GMT</pubDate></item>",
            item("https://www.nass.usda.gov/news/yields", title="Wheat harvest data"),
        ])
        self.assertEqual([x.title for x in parse_official_rss(raw, now=NOW)], ["Wheat harvest data"])

    def test_related_location_and_entity_names_are_excluded_at_ingestion(self):
        raw = rss([
            item("https://www.nass.usda.gov/news/gaza-harvest", title="Gaza harvest estimates"),
            item("https://www.nass.usda.gov/news/cabinet-brief", title="White House crop briefing"),
            "<item><title>Regional crop report</title>"
            "<link>https://www.nass.usda.gov/news/region</link>"
            "<description>Knesset discussion</description>"
            "<pubDate>Sun, 08 Nov 2026 10:00:00 GMT</pubDate></item>",
            item("https://www.nass.usda.gov/news/normal", title="Agricultural production index"),
        ])
        self.assertEqual(
            [row.title for row in parse_official_rss(raw, now=NOW)],
            ["Agricultural production index"],
        )

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

    def test_fao_observed_rss_date_with_z_timezone_accepted(self):
        fao = OFFICIAL_FEEDS[1]
        raw = rss([item(
            "https://www.fao.org/newsroom/detail/fao-food-price-index-edges-down-in-october-amid-subdued-demand/en",
            date="Fri, 06 Nov 2026 12:00:00 Z",
            title="FAO Food Price Index edges down in October amid subdued demand",
        )])
        rows = parse_official_rss(raw, feed=fao, now=NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].published_at.isoformat(), "2026-11-06T12:00:00+00:00")

    def test_editorial_ids_are_source_specific_and_stable(self):
        usda = parse_official_rss(rss([item("https://www.nass.usda.gov/new")]), now=NOW)[0]
        fao = parse_official_rss(
            rss([item("https://www.fao.org/newsroom/detail/new/en")]),
            feed=OFFICIAL_FEEDS[1], now=NOW,
        )[0]
        usda_id, usda_slug = editorial_identity(usda)
        fao_id, fao_slug = editorial_identity(fao)
        self.assertTrue(usda_id.startswith("official-usda-news:"))
        self.assertTrue(usda_slug.startswith("usda-news-"))
        self.assertTrue(fao_id.startswith("official-fao-news:"))
        self.assertTrue(fao_slug.startswith("fao-news-"))
        self.assertEqual(editorial_identity(usda), (usda_id, usda_slug))

    def test_unknown_feed_cannot_gain_editorial_identity(self):
        from dataclasses import replace
        usda = parse_official_rss(rss([item("https://www.nass.usda.gov/new")]), now=NOW)[0]
        with self.assertRaises(ValueError):
            editorial_identity(replace(usda, feed_url="https://untrusted.example/rss"))

    def test_one_feed_failure_retains_other_source(self):
        class Response:
            url = OFFICIAL_FEEDS[0].url

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def read(self, _):
                return rss([item("https://www.nass.usda.gov/new")])

        class Opener:
            def open(self, request, timeout):
                if "fao.org" in request.full_url:
                    raise TimeoutError("feed temporarily unavailable")
                return Response()

        with patch("core.news_feed_reader.build_opener", return_value=Opener()), patch(
            "core.news_feed_reader.datetime"
        ) as clock:
            clock.now.return_value = NOW
            report = fetch_official_news()
        self.assertEqual(report.feeds_ok, 1)
        self.assertEqual(len(report.items), 1)
        self.assertEqual(len(report.feed_errors), 1)

    def test_rss_redirects_reject_other_hosts_and_http(self):
        handler = _OfficialRedirectsOnly(OFFICIAL_FEEDS[1].allowed_hosts)
        request = Request(OFFICIAL_FEEDS[1].url)
        for redirect in (
            "https://evil.example/latest",
            "http://www.fao.org/latest",
            "https://www.fao.org.evil.example/latest",
            "https://admin@www.fao.org/latest",
        ):
            with self.subTest(redirect=redirect), self.assertRaises(ValueError):
                handler.redirect_request(request, None, 302, "Found", {}, redirect)

    def test_rss_redirect_allows_approved_https_host(self):
        handler = _OfficialRedirectsOnly(OFFICIAL_FEEDS[1].allowed_hosts)
        request = Request(OFFICIAL_FEEDS[1].url)
        new_request = handler.redirect_request(
            request, None, 302, "Found", {}, "https://www.fao.org/feeds/fao-newsroom-rss"
        )
        self.assertEqual(new_request.full_url, "https://www.fao.org/feeds/fao-newsroom-rss")


if __name__ == "__main__":
    unittest.main()
