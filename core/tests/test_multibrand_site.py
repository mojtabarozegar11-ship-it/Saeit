from django.test import RequestFactory, SimpleTestCase, override_settings
from core.brand import brand_for_request
from core.brand_views import branded_home

@override_settings(ALLOWED_HOSTS=["zomorodmelal.ir", "mojplaywin.com", "www.mojplaywin.com", "testserver"])
class MultiBrandRoutingTests(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def test_mojplaywin_host_resolves_independent_brand(self):
        request = self.rf.get("/", HTTP_HOST="mojplaywin.com")
        brand = brand_for_request(request)
        self.assertIsNotNone(brand)
        self.assertEqual(brand.code, "mojplaywin")
        self.assertEqual(brand.template, "brands/mojplaywin/home.html")

    def test_mojplaywin_home_uses_english_independent_template(self):
        response = branded_home(self.rf.get("/", HTTP_HOST="mojplaywin.com"))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("MojPlayWin", body)
        self.assertIn("Play the world.", body)
        self.assertNotIn("Zomorodmelal", body)

    def test_primary_brand_keeps_existing_home(self):
        response = branded_home(self.rf.get("/", HTTP_HOST="zomorodmelal.ir"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("Zomorodmelal", response.content.decode("utf-8"))
