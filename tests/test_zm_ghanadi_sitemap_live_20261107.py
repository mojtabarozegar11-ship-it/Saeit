"""Offline regression checks for the guarded live Ghanadi sitemap patch."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


SOURCE = Path(__file__).resolve().parents[1] / 'scripts' / 'zm_ghanadi_sitemap_live_20261107.py'
spec = importlib.util.spec_from_file_location('ghanadi_sitemap_guard', SOURCE)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class GhanadiSitemapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        home = Path(self.temp.name)
        guard.HOME = home
        guard.ROOT = home / 'public_html'
        guard.SITEMAP = guard.ROOT / 'sitemap.xml'
        guard.BACKUP = home / '.backups/ghanadi'
        guard.LOCK = home / '.locks/ghanadi.lock'
        guard.ROOT.mkdir()
        for page in guard.PAGES:
            target = guard.ROOT / page
            target.mkdir(parents=True)
            (target / 'index.html').write_text('<html>real page</html>', encoding='utf-8')
        self.original = (b'<?xml version="1.0" encoding="utf-8"?>\n'
                         b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                         b'<url><loc>https://zomorodmelal.ir/</loc></url></urlset>\n')
        guard.SITEMAP.write_bytes(self.original)

    def test_add_once_preserves_old_urls_then_reverses_exactly(self):
        guard.apply('123456')
        after = guard.SITEMAP.read_bytes()
        locs = guard.locations(after)
        self.assertEqual(locs[0], 'https://zomorodmelal.ir/')
        self.assertEqual(locs[1:], list(guard.URLS))
        guard.apply('123457')
        self.assertEqual(guard.SITEMAP.read_bytes(), after)
        self.assertFalse((guard.BACKUP / '123457').exists())
        guard.rollback('123456')
        self.assertEqual(guard.SITEMAP.read_bytes(), self.original)

    def test_concurrent_change_prevents_unsafe_rollback(self):
        guard.apply('123458')
        changed = guard.SITEMAP.read_bytes() + b'\n'
        guard.SITEMAP.write_bytes(changed)
        with self.assertRaisesRegex(RuntimeError, 'ROLLBACK_REFUSED'):
            guard.rollback('123458')
        self.assertEqual(guard.SITEMAP.read_bytes(), changed)

    def test_invalid_xml_and_symlink_pages_are_rejected(self):
        guard.SITEMAP.write_text('<broken>', encoding='utf-8')
        with self.assertRaises(ET.ParseError):
            guard.apply('123459')
        guard.SITEMAP.write_bytes(self.original)
        (guard.ROOT / 'ghanadi' / 'index.html').unlink()
        (guard.ROOT / 'ghanadi' / 'index.html').symlink_to(guard.SITEMAP)
        with self.assertRaisesRegex(RuntimeError, 'SYMLINK_PATH'):
            guard.apply('123460')


if __name__ == '__main__':
    unittest.main()
