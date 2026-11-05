"""Local binary-only relay tests; no live database or backup is accessed."""
import io
import unittest

from scripts.mpw_isolated_sql_progress_20261105 import relay


class ShortWriter(io.BytesIO):
    def write(self, payload):
        return super().write(payload[:3])


class IsolatedRelayTests(unittest.TestCase):
    def test_exact_stream_with_short_writes_no_payload_in_diagnostics(self):
        private = b"INSERT INTO customer VALUES ('NEVER_LOG_THIS_SECRET');" * 20
        out = ShortWriter()
        events = []
        copied = relay(io.BytesIO(private), out, events.append,
                       milestone=100, maximum=2000)
        self.assertEqual(copied, len(private))
        self.assertEqual(out.getvalue(), private)
        self.assertEqual(events[-1], "MPW_ISOLATED_SQL_RELAY=EOF_STREAMED_NOT_RESTORE_PROOF")
        self.assertNotIn("NEVER_LOG_THIS_SECRET", str(events))
        self.assertNotIn("INSERT", str(events))

    def test_excess_bytes_fail_before_writing_excess_block(self):
        events = []
        out = io.BytesIO()
        with self.assertRaises(ValueError):
            relay(io.BytesIO(b"private SQL " * 30), out, events.append,
                  milestone=10, maximum=100)
        self.assertEqual(out.getvalue(), b"")
        self.assertEqual(events, ["MPW_ISOLATED_SQL_RELAY=LIMIT_EXCEEDED"])

    def test_empty_source_cannot_be_misreported_as_restored(self):
        events = []
        copied = relay(io.BytesIO(), io.BytesIO(), events.append,
                       milestone=10, maximum=100)
        self.assertEqual(copied, 0)
        self.assertEqual(events, ["MPW_ISOLATED_SQL_RELAY=EOF_STREAMED_NOT_RESTORE_PROOF"])


if __name__ == "__main__":
    unittest.main()
