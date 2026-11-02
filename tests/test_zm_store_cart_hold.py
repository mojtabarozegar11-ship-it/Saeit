"""Offline HTTP contract for the Zomorod store's non-transactional cart HOLD."""
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "content/zomorod-v11/store_cart_index.php"


@unittest.skipUnless(shutil.which("php"), "PHP CLI required")
class StoreCartHoldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        docroot = Path(cls.tmp.name)
        target = docroot / "store/cart/index.php"
        target.parent.mkdir(parents=True)
        shutil.copyfile(SOURCE, target)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        cls.url = f"http://127.0.0.1:{port}/store/cart/"
        cls.proc = subprocess.Popen(
            ["php", "-S", f"127.0.0.1:{port}", "-t", str(docroot)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(50):
            if cls.proc.poll() is not None:
                break
            try:
                with urllib.request.urlopen(cls.url, timeout=1) as response:
                    if response.status == 200:
                        return
            except (OSError, urllib.error.URLError):
                time.sleep(0.1)
        cls.tearDownClass()
        raise RuntimeError("Local PHP cart fixture did not start")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "proc") and cls.proc.poll() is None:
            cls.proc.terminate()
            try:
                cls.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                cls.proc.kill()
                cls.proc.wait(timeout=3)
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def test_get_is_informational_200_without_checkout(self):
        with urllib.request.urlopen(self.url, timeout=5) as response:
            body = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertIn("no-store", response.headers["Cache-Control"])
            self.assertIn("noindex", response.headers["X-Robots-Tag"])
            self.assertEqual(response.headers["X-Frame-Options"], "DENY")
            self.assertIn("form-action 'none'", response.headers["Content-Security-Policy"])
        self.assertIn("ثبت سفارش و پرداخت اینترنتی در حال حاضر غیرفعال است", body)
        self.assertIn('href="/store/"', body)
        self.assertNotIn("<form", body.lower())
        self.assertNotIn("<script", body.lower())
        self.assertNotIn("checkout", body.lower())
        self.assertNotIn("payment_intent", body.lower())

    def test_post_is_rejected_without_receipt(self):
        request = urllib.request.Request(self.url, data=b"sku=invalid&amount=1", method="POST")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(ctx.exception.code, 405)
        self.assertEqual(ctx.exception.headers["Allow"], "GET, HEAD")

    def test_head_is_allowed(self):
        request = urllib.request.Request(self.url, method="HEAD")
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), b"")

    def test_query_cannot_inject_markup_or_order(self):
        payload = "%3Cscript%3Ealert(1)%3C%2Fscript%3E"
        with urllib.request.urlopen(self.url + "?sku=" + payload, timeout=5) as response:
            body = response.read().decode("utf-8")
        self.assertNotIn("alert(1)", body)
        self.assertNotIn("sku=", body)


if __name__ == "__main__":
    unittest.main()
