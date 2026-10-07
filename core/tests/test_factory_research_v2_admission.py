"""Regression coverage for the durable source-job admission boundary.

Run only after deployed model/code reconciliation. No network or production DB needed.
"""
from django.test import SimpleTestCase
from core.factory_research_v2 import acceptable_discovery_url


class DiscoveryURLAdmissionTests(SimpleTestCase):
    def test_accepts_public_https_hostname_syntax(self):
        self.assertTrue(acceptable_discovery_url('https://www.example.com/guide?q=inventory'))

    def test_rejects_non_https_and_credentials(self):
        for url in ('http://example.com/', 'ftp://example.com/',
                    'https://user:pass@example.com/', 'https://user@example.com/'):
            with self.subTest(url=url):
                self.assertFalse(acceptable_discovery_url(url))

    def test_rejects_local_hosts_and_ip_literals(self):
        for url in ('https://localhost/', 'https://db.internal/',
                    'https://192.168.1.1/', 'https://127.0.0.1/',
                    'https://[::1]/', 'https://service.local/'):
            with self.subTest(url=url):
                self.assertFalse(acceptable_discovery_url(url))

    def test_rejects_unsafe_url_structure(self):
        for url in ('https://example.com:444/', 'https://example.com/#fragment',
                    'https://example.com/\nadmin', 'https://example.com./',
                    'https://example.com:bad/', 'https://example.com/\x00'):
            with self.subTest(url=url):
                self.assertFalse(acceptable_discovery_url(url))

    def test_rejects_non_string_and_oversized_url(self):
        self.assertFalse(acceptable_discovery_url(None))
        self.assertFalse(acceptable_discovery_url('https://example.com/' + 'a' * 2000))
