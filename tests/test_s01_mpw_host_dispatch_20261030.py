"""S-01 production /store/ host dispatch regression, without network/DB/deploy."""
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from core import commerce_views
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
            "mojplaywin.com..", "localhost", "127.0.0.1",
        ):
            with self.subTest(host=host):
                self.assertFalse(views._is_mojplaywin(self.request(host)))

    def test_public_store_route_uses_mojplaywin_for_canonical_dns_hosts(self):
        # config.urls sends /store/ to commerce_views.store_home, NOT to
        # mojplaywin_views.branded_store_dispatch. Test the actual entrypoint.
        for host in ("mojplaywin.com", "MOJPLAYWIN.COM.", "www.mojplaywin.com.:443"):
            with self.subTest(host=host):
                req = self.request(host)
                with patch.object(views, "store", return_value="MPW") as mpw, \
                     patch.object(commerce_views.Product.objects, "filter") as filter_:
                    self.assertEqual(commerce_views.store_home(req), "MPW")
                    mpw.assert_called_once_with(req)
                    filter_.assert_not_called()

    def test_public_store_route_preserves_other_brand(self):
        for host in ("zomorodmelal.ir", "evilmojplaywin.com", "mojplaywin.com.."):
            with self.subTest(host=host):
                req = self.request(host)
                with patch.object(views, "store", return_value="MPW") as mpw, \
                     patch.object(commerce_views.Product.objects, "filter") as filter_, \
                     patch.object(commerce_views, "render", return_value="OTHER") as render_:
                    filter_.return_value.order_by.return_value = ["ZM"]
                    self.assertEqual(commerce_views.store_home(req), "OTHER")
                    mpw.assert_not_called()
                    filter_.assert_called_once_with(active=True)
                    render_.assert_called_once_with(req, "core/store.html", {"products": ["ZM"]})
