from django.test import TestCase
from django.urls import reverse

from core.models import FarnazInquiry, FarnazOffer


class FarnazSiteTests(TestCase):
    def test_landing_page_has_complete_content_and_no_live_payment_claim(self):
        response = self.client.get(reverse("farnaz_home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Architectural drafting")
        self.assertContains(response, "consultation")
        self.assertContains(response, "CONCEPT SAMPLE")
        self.assertContains(response, "Checkout will be enabled after the business selects a payment provider")
        self.assertFalse(FarnazOffer.objects.filter(checkout_enabled=True).exists())

    def test_valid_inquiry_is_saved_for_django_admin(self):
        response = self.client.post(reverse("farnaz_inquiry"), {
            "name": "Test User",
            "phone": "09120000000",
            "email": "demo@example.com",
            "category": FarnazInquiry.Category.DRAWING,
            "message": "Request to review a drawing",
            "consent": "on",
        })
        self.assertRedirects(response, "/farnaz/?sent=1#contact")
        inquiry = FarnazInquiry.objects.get()
        self.assertEqual(inquiry.status, FarnazInquiry.Status.NEW)
        self.assertEqual(inquiry.phone, "09120000000")

    def test_honeypot_does_not_create_a_lead(self):
        self.client.post(reverse("farnaz_inquiry"), {"website": "spam"})
        self.assertEqual(FarnazInquiry.objects.count(), 0)
