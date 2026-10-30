"""S-01 canonical host routing regressions; no network, database or deploy."""
from types import ModuleType
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from core import mojplaywin_views as views


class MojPlayWinHostDispatchTests(SimpleTestCase):
    def request(self, host):
        return Mock(get_host=Mock(return_value=host))

    def test_canonical_host_with_dns_final_dot_is_mojplaywin(self):
        for host in (
            "mojplaywin.com", "www.mojplaywin.com",
            "MOJPLAYWIN.COM.", "WWW.MOJPLAYWIN.COM.:443",
            "mojplaywin.com:8443",
        ):
            with self.subTest(host=host):
                self.assertTrue(views._is_mojplaywin(self.request(host)))

    def test_lookalike_and_other_hosts_do_not_get_mojplaywin_dispatch(self):
        for host in (
            "zomorodmelal.ir", "evilmojplaywin.com",
            "mojplaywin.com.evil.example", "mojplaywin.com..evil",
            "mojplaywin.com..",
            "localhost", "127.0.0.1",
        ):
            with self.subTest(host=host):
                self.assertFalse(views._is_mojplaywin(self.request(host)))

    @staticmethod
    def other_brand_stub():
        # No brand_views.py in this checkout branch.  Simulate the optional
        # cross-brand module without importing or changing any site source.
        module = ModuleType("core.brand_views")
        module.branded_store = Mock(return_value="OTHER")
        return module

    def test_canonical_store_dispatch_preserves_brand_isolation(self):
        req = self.request("mojplaywin.com.")
        other = self.other_brand_stub()
        with patch.object(views, "store", return_value="MPW") as mpw, \
             patch.dict("sys.modules", {"core.brand_views": other}):
            self.assertEqual(views.branded_store_dispatch(req), "MPW")
            mpw.assert_called_once_with(req)
            other.branded_store.assert_not_called()

    def test_other_host_never_receives_mojplaywin_store(self):
        req = self.request("zomorodmelal.ir")
        other = self.other_brand_stub()
        with patch.object(views, "store", return_value="MPW") as mpw, \
             patch.dict("sys.modules", {"core.brand_views": other}):
            self.assertEqual(views.branded_store_dispatch(req), "OTHER")
            mpw.assert_not_called()
            other.branded_store.assert_called_once_with(req)
