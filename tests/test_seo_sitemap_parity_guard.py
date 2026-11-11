"""Regression tests for the no-network, fail-closed sitemap parity guard."""

import tempfile
import unittest
from pathlib import Path

from scripts.seo_sitemap_parity_guard import SitemapParityError, compare, main, read_urls


NS = 'http://www.sitemaps.org/schemas/sitemap/0.9'
HOST = 'https://mojplaywin.com'


def sitemap(urls):
    return f'<urlset xmlns="{NS}">' + ''.join(
        f'<url><loc>{url}</loc></url>' for url in urls
    ) + '</urlset>'


class SitemapParityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.before = Path(self.tmp.name) / 'before.xml'
        self.after = Path(self.tmp.name) / 'after.xml'

    def write(self, old, new):
        self.before.write_text(sitemap(old), encoding='utf-8')
        self.after.write_text(sitemap(new), encoding='utf-8')

    def test_added_paths_allowed_without_losing_existing_urls(self):
        self.write([HOST+'/', HOST+'/store/'], [HOST+'/', HOST+'/store/', HOST+'/games/'])
        result = compare(self.before, self.after, HOST, ['/store/'])
        self.assertEqual((result['status'], result['added_count'], result['removed_count']), ('PASS', 1, 0))

    def test_removed_old_path_blocks_release(self):
        self.write([HOST+'/', HOST+'/store/'], [HOST+'/'])
        result = compare(self.before, self.after, HOST, [])
        self.assertEqual((result['status'], result['removed_count']), ('HOLD', 1))
        self.assertEqual(main(['--before', str(self.before), '--after', str(self.after), '--origin', HOST]), 1)

    def test_required_product_path_blocks_release_even_if_absent_before(self):
        self.write([HOST+'/'], [HOST+'/'])
        result = compare(self.before, self.after, HOST, ['/store/product/72/'])
        self.assertEqual(result['missing_required_count'], 1)
        self.assertEqual(result['status'], 'HOLD')

    def test_cross_host_url_rejected_in_each_snapshot(self):
        self.write([HOST+'/'], [HOST+'/', 'https://zomorodmelal.ir/services/'])
        with self.assertRaises(SitemapParityError):
            compare(self.before, self.after, HOST, [])
        self.write(['https://zomorodmelal.ir/'], [HOST+'/'])
        with self.assertRaises(SitemapParityError):
            compare(self.before, self.after, HOST, [])

    def test_duplicate_loc_rejected(self):
        self.write([HOST+'/'], [HOST+'/', HOST+'/'])
        with self.assertRaises(SitemapParityError):
            read_urls(self.after, 'mojplaywin.com')

    def test_malformed_xml_and_empty_sitemaps_rejected(self):
        self.before.write_text('<urlset>', encoding='utf-8')
        self.after.write_text(sitemap([HOST+'/']), encoding='utf-8')
        with self.assertRaises(SitemapParityError):
            compare(self.before, self.after, HOST, [])
        self.before.write_text(sitemap([]), encoding='utf-8')
        with self.assertRaises(SitemapParityError):
            compare(self.before, self.after, HOST, [])

    def test_query_fragments_and_http_rejected(self):
        for invalid_url in [HOST+'/?page=2', HOST+'/#fragment', 'http://mojplaywin.com/']:
            with self.subTest(invalid_url=invalid_url):
                self.write([HOST+'/'], [invalid_url])
                with self.assertRaises(SitemapParityError):
                    compare(self.before, self.after, HOST, [])

    def test_symlink_snapshot_rejected(self):
        self.write([HOST+'/'], [HOST+'/'])
        linked = Path(self.tmp.name) / 'link.xml'
        linked.symlink_to(self.before)
        with self.assertRaises(SitemapParityError):
            compare(linked, self.after, HOST, [])


if __name__ == '__main__':
    unittest.main()
