import importlib.util
import io
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError

SRC = Path(__file__).resolve().parents[1] / "scripts" / "zomorod_public_readiness_20261019.py"
spec = importlib.util.spec_from_file_location("zomorod_readiness", SRC)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeResponse:
    def __init__(self, status=200, url="https://zomorodmelal.ir/"):
        self.status = status
        self.url = url
        self.headers = {"Content-Type": "text/html; charset=utf-8",
                        "strict-transport-security": "max-age=86400"}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def getcode(self):
        return self.status

    def geturl(self):
        return self.url

    def read(self, limit):
        assert limit <= 2048
        return b"<html><head><title>ok</title></head></html>"


class ZomorodReadinessTests(unittest.TestCase):
    def test_allowlisted_success(self):
        entry = module.inspect("/", lambda req, timeout: FakeResponse())
        self.assertTrue(entry["ok"])
        self.assertTrue(entry["security_headers_present"]["strict-transport-security"])

    def test_http_error_fail_closed(self):
        def bad(req, timeout):
            raise HTTPError(req.full_url, 503, "down", {}, io.BytesIO())
        entry = module.inspect("/", bad)
        self.assertFalse(entry["ok"])
        self.assertEqual(entry["status"], 503)

    def test_network_failure_fail_closed(self):
        entry = module.inspect("/", lambda req, timeout: (_ for _ in ()).throw(URLError("offline")))
        self.assertFalse(entry["ok"])
        self.assertEqual(entry["status"], 0)

    def test_external_redirect_fails(self):
        entry = module.inspect("/", lambda req, timeout: FakeResponse(url="https://other.example/"))
        self.assertFalse(entry["ok"])

    def test_private_path_rejected_before_network(self):
        with self.assertRaises(ValueError):
            module.inspect("/admin/")


if __name__ == "__main__":
    unittest.main()
