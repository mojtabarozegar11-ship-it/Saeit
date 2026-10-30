import unittest
from g01_s01_offline_a11y_r36 import scan

class TestA11y(unittest.TestCase):
    def test_safe_markup(self):
        self.assertTrue(scan('<button aria-label="Download"></button><a href="file.pdf" download>PDF</a><a href="/help" target="_blank" rel="noopener">Help</a>')['pass'])
    def test_empty_icon_button(self):
        self.assertEqual(scan('<button><svg></svg></button>')['counts']['unlabeled_buttons'], 1)
    def test_external_blank_link(self):
        self.assertEqual(scan('<a href="/" target="_blank">Open</a>')['counts']['blank_links_without_noopener'], 1)
    def test_missing_download_target(self):
        self.assertEqual(scan('<a download>PDF</a>')['counts']['download_links_missing_href'], 1)
    def test_no_source_content_leak(self):
        self.assertNotIn('customer',str(scan('<button>customer</button>')))

if __name__ == '__main__': unittest.main()
