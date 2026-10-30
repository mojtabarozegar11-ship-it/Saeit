"""Offline-only classification regression; no SSH, credentials or network."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from s01_ssh_error_classify import classify


class ClassifierTests(unittest.TestCase):
    def test_auth(self):
        self.assertEqual(classify("Permission denied (publickey)."), "AUTH_REJECTED")

    def test_host_key(self):
        self.assertEqual(classify("Host key verification failed."), "HOST_KEY_REJECTED")

    def test_network(self):
        self.assertEqual(classify("connect to host: Connection timed out"), "TRANSPORT_UNREACHABLE")

    def test_banner(self):
        self.assertEqual(classify("kex_exchange_identification: read: Connection reset"), "BANNER_OR_KEX_FAILED")

    def test_dns(self):
        self.assertEqual(classify("Could not resolve hostname relay"), "DNS_RESOLUTION_FAILED")

    def test_secret_never_returned(self):
        self.assertEqual(classify("token=private-example /home/owner/secret"), "UNKNOWN_SAFE_FAILURE")

    def test_empty(self):
        self.assertEqual(classify(""), "UNKNOWN_SAFE_FAILURE")


if __name__ == "__main__":
    unittest.main()
