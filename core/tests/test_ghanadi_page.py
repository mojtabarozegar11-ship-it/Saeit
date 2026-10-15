from django.contrib.staticfiles import finders
from django.test import TestCase


class GhanadiStorefrontTests(TestCase):
    def test_storefront_is_served_at_its_canonical_company_path(self):
        response = self.client.get("/ghanadi/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "قنادی زمرد")
        self.assertContains(response, 'https://zomorodmelal.ir/ghanadi/')
        self.assertContains(response, "کوکی شکلات تلخ")
        self.assertContains(response, "کتابچهٔ ۱۲ دستور کوکی")

    def test_all_storefront_illustrations_are_collected(self):
        for name in ("box.svg", "cake.svg", "cafe.svg", "cookie.svg"):
            with self.subTest(name=name):
                self.assertIsNotNone(finders.find(f"site/ghanadi/{name}"))
