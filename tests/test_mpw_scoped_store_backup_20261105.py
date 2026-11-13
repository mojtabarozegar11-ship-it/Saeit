"""Pure safety invariants; these tests never contact the production database."""
import gzip
import io
import unittest

try:
    from scripts.mpw_scoped_store_backup_source_20261105 import fk_parent_closure
    from scripts.mpw_scoped_store_backup_vps_20261105 import (
        MARKER, inspect_plain_gzip, paths,
    )
    from scripts.mpw_scoped_store_restore_verify_20261105 import orphan_query
except ModuleNotFoundError:
    # Equivalent stand-alone source tree used for offline code review.
    from mpw_scoped_store_backup_source_20261105 import fk_parent_closure
    from mpw_scoped_store_backup_vps_20261105 import (
        MARKER, inspect_plain_gzip, paths,
    )
    from mpw_scoped_store_restore_verify_20261105 import orphan_query


class ScopedStoreTests(unittest.TestCase):
    def test_fk_transitive_closure(self):
        graph = [("order", "product"), ("product", "report"), ("irrelevant", "big")]
        self.assertEqual(fk_parent_closure({"order"}, graph),
                         {"order", "product", "report"})

    def test_scoped_id_guard(self):
        paths("mpw_store_20261105T163000Z_0123456789abcdef")
        for bad in ("../x", "mojplaywin_20261105T163000Z_0123456789abcdef", "x"):
            with self.assertRaises(RuntimeError):
                paths(bad)

    def test_gzip_footer_and_checksum(self):
        payload = b"CREATE TABLE `core_order` (id int);\n" * 60 + MARKER
        encoded = gzip.compress(payload, compresslevel=1)
        output = io.BytesIO()
        report = inspect_plain_gzip(iter((encoded[:30], encoded[30:])), output)
        self.assertEqual(output.getvalue(), encoded)
        self.assertEqual(report["sql_bytes"], len(payload))
        self.assertEqual(report["gzip_bytes"], len(encoded))

    def test_truncated_gzip_rejected(self):
        payload = gzip.compress(b"x" * 1600 + MARKER)
        with self.assertRaises(RuntimeError):
            inspect_plain_gzip([payload[:-3]])

    def test_missing_footer_rejected(self):
        with self.assertRaises(RuntimeError):
            inspect_plain_gzip([gzip.compress(b"x" * 2000)])

    def test_multicolumn_fk_query(self):
        q = orphan_query([
            ("child", "a", "parent", "aa"),
            ("child", "b", "parent", "bb"),
        ])
        self.assertIn("c.`a`=p.`aa` AND c.`b`=p.`bb`", q)
        self.assertIn("c.`a` IS NOT NULL AND c.`b` IS NOT NULL", q)

    def test_identifier_injection_rejected(self):
        with self.assertRaises(RuntimeError):
            orphan_query([("x;DROP", "a", "parent", "id")])


if __name__ == "__main__":
    unittest.main()
