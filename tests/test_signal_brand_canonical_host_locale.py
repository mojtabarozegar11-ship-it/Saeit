"""17 signal-market brands must never derive country/merchant from a spoofed host."""
from django.test import RequestFactory, SimpleTestCase, override_settings
from core.financial_brand_pages import financial_brand_page

@override_settings(ALLOWED_HOSTS=["*"], USE_X_FORWARDED_HOST=False)
class FinancialMarketHostTests(SimpleTestCase):
    def setUp(self):
        self.factory=RequestFactory()

    def page(self, host, forwarded=None):
        kw={"HTTP_HOST":host}
        if forwarded is not None:
            kw["HTTP_X_FORWARDED_HOST"]=forwarded
        request=self.factory.get("/saman/market-signals/",**kw)
        return financial_brand_page(request,"saman","host","signals").content.decode()

    def test_01_exact_iran_host_uses_fa(self):
        self.assertIn('lang="fa"',self.page("zomorodmelal.ir"))

    def test_02_www_iran_host_uses_fa(self):
        self.assertIn('lang="fa"',self.page("www.zomorodmelal.ir"))

    def test_03_primary_mojplaywin_uses_en(self):
        self.assertIn('lang="en"',self.page("mojplaywin.com"))

    def test_04_www_mojplaywin_uses_en(self):
        self.assertIn('lang="en"',self.page("www.mojplaywin.com"))

    def test_05_substring_lookalike_not_iran(self):
        self.assertIn('lang="en"',self.page("evilzomorodmelal.ir.attacker.example"))

    def test_06_forwarded_iran_header_not_override_mojplaywin(self):
        self.assertIn('lang="en"',self.page("mojplaywin.com","zomorodmelal.ir"))

    def test_07_forwarded_mojplaywin_not_override_iran(self):
        self.assertIn('lang="fa"',self.page("zomorodmelal.ir","mojplaywin.com"))

    def test_08_subdomain_under_iran_not_implicitly_main_merchant(self):
        self.assertIn('lang="en"',self.page("sales.zomorodmelal.ir"))
