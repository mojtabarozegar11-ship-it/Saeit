"""Source-independent business lead intake checks; no external emails or payments."""
from pathlib import Path

from django.test import TestCase
from django.urls import reverse

from core.company_inquiry_models import CompanyInquiry

ROOT = Path(__file__).resolve().parents[1]


class CommercialLeadIntakeQualityTests(TestCase):
    def payload(self, **overrides):
        value = {
            "kind": "commercial",
            "name": "  Customer   Example  ",
            "organization": "  Farm   Group  ",
            "email": "Buyer@EXAMPLE.ORG",
            "phone": "",
            "subject": "  Request   for  quotation  ",
            "message": "I would like a verified price quotation and scope.",
        }
        value.update(overrides)
        return value

    def send(self, **kwargs):
        return self.client.post(reverse("company"), self.payload(**kwargs))

    def test_01_valid_request_persists_new_lead(self):
        self.assertEqual(self.send().status_code, 302)
        self.assertEqual(CompanyInquiry.objects.count(), 1)
        self.assertEqual(CompanyInquiry.objects.get().status, "new")

    def test_02_normalizes_name_spaces(self):
        self.send()
        self.assertEqual(CompanyInquiry.objects.get().name, "Customer Example")

    def test_03_normalizes_organization_spaces(self):
        self.send()
        self.assertEqual(CompanyInquiry.objects.get().organization, "Farm Group")

    def test_04_normalizes_subject_spaces(self):
        self.send()
        self.assertEqual(CompanyInquiry.objects.get().subject, "Request for quotation")

    def test_05_domain_is_case_normalized_without_changing_email_local_part(self):
        self.send()
        self.assertEqual(CompanyInquiry.objects.get().email, "Buyer@example.org")

    def test_06_all_five_declared_inquiry_types_are_accepted(self):
        for kind in ("research", "technology", "project", "commercial", "media"):
            with self.subTest(kind=kind):
                response = self.send(kind=kind)
                self.assertEqual(response.status_code, 302)
        self.assertEqual(CompanyInquiry.objects.count(), 5)

    def test_07_persian_text_survives_unchanged(self):
        self.send(name="فروشگاه کشاورزی", subject="استعلام خدمات آبیاری")
        row = CompanyInquiry.objects.get()
        self.assertEqual(row.name, "فروشگاه کشاورزی")
        self.assertEqual(row.subject, "استعلام خدمات آبیاری")

    def test_08_phone_international_format_is_accepted(self):
        self.send(phone="+98 (912) 123-4567")
        self.assertEqual(CompanyInquiry.objects.get().phone, "+98 (912) 123-4567")

    def test_09_blank_phone_keeps_inquiry_usable(self):
        self.send(phone="")
        self.assertEqual(CompanyInquiry.objects.get().phone, "")

    def test_10_phone_letters_are_rejected(self):
        self.send(phone="+98-call-me")
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_11_phone_too_short_is_rejected(self):
        self.send(phone="123456")
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_12_phone_too_long_is_rejected(self):
        self.send(phone="1234567890123456")
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_13_honeypot_content_is_rejected(self):
        self.send(website="https://bots.example")
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_14_empty_honeypot_remains_backward_compatible(self):
        self.send(website="")
        self.assertEqual(CompanyInquiry.objects.count(), 1)

    def test_15_honeypot_whitespace_does_not_block_human(self):
        self.send(website="    ")
        self.assertEqual(CompanyInquiry.objects.count(), 1)

    def test_16_oversized_honeypot_rejected(self):
        self.send(website="a" * 129)
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_17_identical_repeat_within_three_minutes_not_reinserted(self):
        self.send()
        self.send()
        self.assertEqual(CompanyInquiry.objects.count(), 1)

    def test_18_distinct_subject_is_not_deduplicated(self):
        self.send()
        self.send(subject="Different request")
        self.assertEqual(CompanyInquiry.objects.count(), 2)

    def test_19_distinct_message_is_not_deduplicated(self):
        self.send()
        self.send(message="A different project with separate drawings.")
        self.assertEqual(CompanyInquiry.objects.count(), 2)

    def test_20_distinct_customer_email_not_deduplicated(self):
        self.send()
        self.send(email="another@example.org")
        self.assertEqual(CompanyInquiry.objects.count(), 2)

    def test_21_distinct_inquiry_kind_not_deduplicated(self):
        self.send()
        self.send(kind="research")
        self.assertEqual(CompanyInquiry.objects.count(), 2)

    def test_22_name_bidi_override_rejected(self):
        self.send(name="Ali\u202eExample")
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_23_subject_bidi_override_rejected(self):
        self.send(subject="Invoice\u202eFake")
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_24_message_bidi_override_rejected(self):
        self.send(message="Please\u2066approve\u2069 the quote.")
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_25_message_crlf_canonicalized(self):
        self.send(message="Item 1\r\nItem 2")
        self.assertEqual(CompanyInquiry.objects.get().message, "Item 1\nItem 2")

    def test_26_message_newline_and_tab_permitted(self):
        self.send(message="Line one\n\tLine two")
        self.assertEqual(CompanyInquiry.objects.get().message, "Line one\n\tLine two")

    def test_27_body_over_twelve_kilobytes_rejected_before_parsing(self):
        response = self.send(message="x" * 13000)
        self.assertEqual(response.status_code, 413)
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_28_maximum_5000_character_message_is_accepted(self):
        self.send(message="x" * 5000)
        self.assertEqual(CompanyInquiry.objects.count(), 1)

    def test_29_5001_character_message_is_rejected(self):
        self.send(message="x" * 5001)
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_30_invalid_email_is_rejected(self):
        self.send(email="not-an-email")
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_31_invalid_kind_is_rejected(self):
        self.send(kind="payment_approved")
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_32_frontend_exposes_privacy_scope_and_no_pretend_payment(self):
        content = (ROOT / "core/templates/core/platform_page.html").read_text("utf-8")
        self.assertIn('name="website"', content)
        self.assertIn('aria-describedby="company-inquiry-privacy"', content)
        self.assertIn("اطلاعات تماس فقط برای بررسی و پاسخ", content)
        self.assertIn('maxlength="5000"', content)
        self.assertIn('type="email" name="email"', content)

    def test_33_no_live_email_or_payment_trigger_in_view(self):
        text = (ROOT / "core/company_content_views.py").read_text("utf-8")
        self.assertNotIn("send_mail(", text)
        self.assertNotIn("create_charge(", text)
        self.assertIn("CompanyInquiry.objects.filter(", text)


if __name__ == "__main__":
    import unittest
    unittest.main()
