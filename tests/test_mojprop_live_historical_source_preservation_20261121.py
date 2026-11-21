"""Immutable snapshot regression for original live English MOJ PROP source.

Historical HTML bytes remain reviewable and are not re-used as a current
payment authorization. This test never contacts the network or any wallet.
"""
import hashlib
from pathlib import Path
import unittest

ARCHIVE = Path(__file__).resolve().parents[1] / "docs/mojprop/historical-static-evidence"
ORIGINALS = (
    "169f4464107da0145fe47cbe5725a6aebbdca79a",
    "aed48d54b7d37b6dfba4d53295d8ffdab53cad83",
)


class EnglishMojPropHistoricalHTMLPreservation(unittest.TestCase):
    def test_pre_change_host_reviewed_static_versions_remain_immutable(self):
        for blob in ORIGINALS:
            with self.subTest(blob=blob):
                src = ARCHIVE / (blob + ".html")
                data = src.read_bytes()
                computed = hashlib.sha1(
                    b"blob " + str(len(data)).encode("ascii") + b"\0" + data
                ).hexdigest()
                self.assertEqual(computed, blob)
                self.assertIn(b"<!doctype html>", data.lower())


if __name__ == "__main__":
    unittest.main()
