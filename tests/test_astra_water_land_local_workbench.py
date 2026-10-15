"""Actual ephemeral loopback HTTP tests for the private crop editor/backend."""
import http.client
import importlib.util
import json
from pathlib import Path
import sys
from threading import Thread
import unittest

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "product_prototypes" / "farm_water_land_margin_audit"
# serve_local.py imports the engine from the same portable extracted ZIP folder.
sys.path.insert(0, str(P))
spec = importlib.util.spec_from_file_location("astra_water_loopback_test", P / "serve_local.py")
local = importlib.util.module_from_spec(spec)
spec.loader.exec_module(local)


class WaterWorkbenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = local.ThreadingHTTPServer(("127.0.0.1", 0), local.Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=5)
        cls.server.server_close()

    def call(self, method, path, payload=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        hdr = {"Host": "127.0.0.1:" + str(self.port)}
        if headers:
            hdr.update(headers)
        conn.request(method, path, body=payload, headers=hdr)
        res = conn.getresponse()
        code, raw = res.status, res.read()
        meta = dict(res.getheaders())
        conn.close()
        return code, raw, meta

    def analyze(self, model):
        return self.call(
            "POST", "/api/analyze",
            json.dumps(model).encode("utf-8"),
            headers={
                "Origin": "http://127.0.0.1:" + str(self.port),
                "Content-Type": "application/json",
            },
        )

    def test_local_browser_assets_and_no_external_ui_dependencies(self):
        for path, expected in (
            ("/", "text/html"), ("/app.js", "text/javascript"),
            ("/style.css", "text/css"), ("/sample.json", "application/json")
        ):
            with self.subTest(path=path):
                code, data, headers = self.call("GET", path)
                self.assertEqual(code, 200)
                self.assertIn(expected, headers["Content-Type"])
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
                self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
                self.assertGreater(len(data), 100)
        _, page, _ = self.call("GET", "/")
        self.assertIn(b"Load fictional example", page)
        self.assertIn(b"id=\"crop-editors\"", page)
        _, code, _ = self.call("GET", "/app.js")
        self.assertIn(b'textContent', code)
        self.assertIn(b'"/api/analyze"', code)
        self.assertNotIn(b"https://", code)

    def test_calculation_roundtrip_uses_exact_same_python_engine(self):
        model = json.loads((P / "example_synthetic.json").read_text())
        status, body, _ = self.analyze(model)
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertEqual(result, local.audit(model))
        self.assertEqual(len(result["water_sensitivity_frontier"]), 5)
        self.assertIsNone(result["quality_score"])
        for flag in ("sale_ready", "store_publication_authorized",
                     "payments_authorized", "market_demand_verified"):
            self.assertIs(result[flag], False)

    def test_imported_malicious_html_is_only_data_not_server_markup(self):
        model = json.loads((P / "example_synthetic.json").read_text())
        model["crops"][0]["name"] = "<img src=x onerror=alert(1)>"
        code, body, headers = self.analyze(model)
        self.assertEqual(code, 200)
        self.assertIn("<img src=x onerror=alert(1)>", body.decode())
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")

    def test_no_cross_origin_submission(self):
        sample = (P / "example_synthetic.json").read_bytes()
        for origin in (None, "https://evil.example", "null",
                       "http://127.0.0.1:1"):
            hdr = {"Content-Type": "application/json"}
            if origin is not None:
                hdr["Origin"] = origin
            code, _, _ = self.call("POST", "/api/analyze", sample, hdr)
            self.assertEqual(code, 403)

    def test_host_confusion_and_hidden_static_paths_denied(self):
        code, _, _ = self.call("GET", "/", headers={"Host": "evil.example"})
        self.assertEqual(code, 403)
        code, _, _ = self.call("GET", "/../water_margin_audit.py")
        self.assertEqual(code, 404)
        code, _, _ = self.call("GET", "/nonexistent")
        self.assertEqual(code, 404)
        code, _, _ = self.call("GET", "/api/analyze")
        self.assertEqual(code, 404)

    def test_malformed_and_oversized_json_rejected(self):
        origin = "http://127.0.0.1:" + str(self.port)
        code, _, _ = self.call(
            "POST", "/api/analyze", b"{}", {
                "Origin": origin, "Content-Type": "text/plain"})
        self.assertEqual(code, 415)
        code, _, _ = self.call(
            "POST", "/api/analyze", b"not a json", {
                "Origin": origin, "Content-Type": "application/json"})
        self.assertEqual(code, 422)
        code, _, _ = self.call(
            "POST", "/api/analyze", b"x" * (local.MAX_REQUEST+1), {
                "Origin": origin, "Content-Type": "application/json"})
        self.assertEqual(code, 413)

    def test_bad_agronomic_data_not_auto_repaired_or_certified(self):
        example = json.loads((P / "example_synthetic.json").read_text())
        example["crops"][0]["water_m3_per_hectare"] = "0"
        code, data, _ = self.analyze(example)
        self.assertEqual(code, 422)
        self.assertEqual(json.loads(data)["error"], "INVALID_INPUT")


if __name__ == "__main__":
    unittest.main()
