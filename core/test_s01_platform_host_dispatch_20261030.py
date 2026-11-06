"""S-01: actual shared platform URL dispatch must preserve both brands.

No network, DB write, payment, factory or production mutation.
"""
from unittest.mock import Mock, patch, sentinel

from django.test import SimpleTestCase

from core import mojplaywin_views
from core.views import platform_page


class SharedPlatformBrandDispatchTests(SimpleTestCase):
    def request(self, host):
        return Mock(get_host=Mock(return_value=host), path="/industry/")

    def test_single_terminal_dns_dot_preserves_mojplaywin_platform(self):
        for host in ("mojplaywin.com", "MOJPLAYWIN.COM.", "www.mojplaywin.com.:443"):
            with self.subTest(host=host):
                request = self.request(host)
                with patch.object(mojplaywin_views, "platform_section",
                                  return_value=sentinel.mpw) as mpw, \
                     patch("core.views.render", return_value=sentinel.zm) as render:
                    self.assertIs(platform_page(request, "industry"), sentinel.mpw)
                    mpw.assert_called_once_with(request, "industry")
                    render.assert_not_called()

    def test_other_brand_and_double_dot_never_render_mojplaywin(self):
        for host in ("zomorodmelal.ir", "mojplaywin.com..", "evilmojplaywin.com"):
            with self.subTest(host=host):
                request = self.request(host)
                with patch.object(mojplaywin_views, "platform_section",
                                  return_value=sentinel.mpw) as mpw, \
                     patch("core.views.render", return_value=sentinel.zm) as render:
                    self.assertIs(platform_page(request, "industry"), sentinel.zm)
                    mpw.assert_not_called()
                    self.assertEqual(render.call_args.args[:2],
                                     (request, "core/platform_page.html"))
