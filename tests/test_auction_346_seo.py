"""Read-only notice 346 routing, copy and SEO regressions."""
from django.test import SimpleTestCase, override_settings


@override_settings(ALLOWED_HOSTS=["testserver", "zomorodmelal.ir", "mojplaywin.com"])
class ResearchAuction346Tests(SimpleTestCase):
    def test_public_notice_exposes_detailed_requirements(self):
        response = self.client.get("/auctions/346/", HTTP_HOST="zomorodmelal.ir")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "مزایده شماره ۳۴۶")
        self.assertContains(response, "zomorodmelal@gmail.com")
        self.assertContains(response, "۵ تا ۱۰ هر ماه")
        self.assertContains(response, "با اعلام قبلی")
        self.assertContains(response, 'application/ld+json')
        self.assertContains(response, 'rel="canonical"')

    def test_index_links_to_notice(self):
        response = self.client.get("/auctions/", HTTP_HOST="zomorodmelal.ir")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/auctions/346/"')

    def test_other_tenant_does_not_expose_notice(self):
        response = self.client.get("/auctions/346/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 404)
