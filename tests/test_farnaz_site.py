from django.test import TestCase
from django.urls import reverse

from farnaz.models import FarnazInquiry, FarnazOffer


class FarnazSiteTests(TestCase):
    def test_landing_page_is_english_and_shows_complete_content(self):
        response = self.client.get(reverse("farnaz:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Architectural drafting")
        self.assertContains(response, "PORTFOLIO CONCEPTS")
        self.assertContains(response, "Checkout will be enabled after the business selects a payment provider")
        self.assertFalse(FarnazOffer.objects.filter(checkout_enabled=True).exists())

    def test_valid_enquiry_is_saved_for_django_admin(self):
        response = self.client.post(reverse("farnaz:inquiry"), {
            "name": "Test User",
            "phone": "+1 604 555 0123",
            "email": "demo@example.com",
            "category": FarnazInquiry.Category.DRAWING,
            "message": "Please review a residential plan",
            "consent": "on",
        })
        self.assertRedirects(response, "/farnaz/?sent=1#contact")
        inquiry = FarnazInquiry.objects.get()
        self.assertEqual(inquiry.status, FarnazInquiry.Status.NEW)
        self.assertEqual(inquiry.phone, "+1 604 555 0123")

    def test_honeypot_does_not_create_a_lead(self):
        self.client.post(reverse("farnaz:inquiry"), {"website": "spam"})
        self.assertEqual(FarnazInquiry.objects.count(), 0)
