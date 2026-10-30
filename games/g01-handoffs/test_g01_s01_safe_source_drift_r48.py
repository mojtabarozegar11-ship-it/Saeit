import contextlib
import io
import json
import pathlib
import tempfile
import unittest
from g01_s01_safe_source_drift_r48 import compare, main, MAX_BYTES

class SourceDriftTests(unittest.TestCase):
    def test_identical(self):
        with tempfile.TemporaryDirectory() as d:
            a = pathlib.Path(d) / 'a'; a.write_text('alpha\nbeta\n')
            self.assertEqual(compare(str(a), str(a))['status'], 'MATCH')
    def test_drift_never_leaks_source(self):
        with tempfile.TemporaryDirectory() as d:
            a = pathlib.Path(d) / 'a'; b = pathlib.Path(d) / 'b'
            secret = 'private-customer-token'
            a.write_text('safe\n' + secret + '\n')
            b.write_text('safe\nchanged-secret\n')
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main(['audit', str(a), str(b)])
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(out.getvalue())['hunk_count'], 1)
            self.assertNotIn(secret, out.getvalue())
            self.assertNotIn(str(a), out.getvalue())
    def test_oversized_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            a = pathlib.Path(d) / 'a'; a.write_bytes(b'x' * (MAX_BYTES + 1))
            with self.assertRaises(ValueError): compare(str(a), str(a))
    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            a = pathlib.Path(d) / 'a'; a.write_text('a')
            b = pathlib.Path(d) / 'b'; b.symlink_to(a)
            with self.assertRaises(ValueError): compare(str(b), str(a))
    def test_invalid_input_redacted(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(['audit', '/missing/private/path', '/another/path']), 3)
        self.assertEqual(json.loads(out.getvalue()), {'status': 'INVALID_INPUT'})

if __name__ == '__main__': unittest.main()
