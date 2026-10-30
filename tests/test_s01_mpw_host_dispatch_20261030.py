"""S-01 canonical host routing regressions; no network, database or deploy."""
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
            "localhost", "127.0.0.1",
        ):
            with self.subTest(host=host):
                self.assertFalse(views._is_mojplaywin(self.request(host)))

    def test_canonical_store_dispatch_preserves_brand_isolation(self):
        req = self.request("mojplaywin.com.")
        with patch.object(views, "store", return_value="MPW") as mpw, \
             patch("core.brand_views.branded_store", return_value="OTHER") as other:
            self.assertEqual(views.branded_store_dispatch(req), "MPW")
            mpw.assert_called_once_with(req)
            other.assert_not_called()

    def test_other_host_never_receives_mojplaywin_store(self):
        req = self.request("zomorodmelal.ir")
        with patch.object(views, "store", return_value="MPW") as mpw, \
             patch("core.brand_views.branded_store", return_value="OTHER") as other:
            self.assertEqual(views.branded_store_dispatch(req), "OTHER")
            mpw.assert_not_called()
            other.assert_called_once_with(req)
