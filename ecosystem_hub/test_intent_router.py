"""Offline Persian/English subject routing must be deterministic and fail-closed."""
from django.test import SimpleTestCase

from .intent_router import normalize, route_instruction, ROUTER_VERSION


class IntentRoutingTests(SimpleTestCase):
    def test_arabic_letters_and_zero_width_spacing_are_normalized(self):
        self.assertEqual(normalize("تأمين‌مواد"), "تأمین مواد")
        self.assertEqual(normalize("  WEB-SITE  "), "web site")

    def test_single_supported_subject_routes_to_authorized_specialist(self):
        decision = route_instruction(
            "کمپین‌های تبلیغات و سرنخ فروش این واحد را بررسی کن",
            {"marketing-performance"},
        )
        self.assertEqual(decision["status"], "matched")
        self.assertEqual(decision["code"], "marketing-performance")
        self.assertEqual(decision["version"], ROUTER_VERSION)

    def test_multi_department_instruction_requires_explicit_choice(self):
        decision = route_instruction(
            "ریسک و بودجه این واحد را بررسی کن",
            {"risk-analyst", "budget-controller"},
        )
        self.assertEqual(decision["status"], "ambiguous")
        self.assertIsNone(decision["code"])
        self.assertEqual(
            set(decision["candidates"]), {"risk-analyst", "budget-controller"},
        )

    def test_forbidden_subject_never_falls_back_to_another_allowed_handler(self):
        result = route_instruction(
            "بازاریابی این واحد", {"risk-analyst", "budget-controller"},
        )
        self.assertEqual(result["status"], "unauthorized")
        self.assertIsNone(result["code"])

    def test_unknown_subject_does_not_generate_an_assistant_claim(self):
        result = route_instruction("سلام، روز خوبی داشته باشید", {"risk-analyst"})
        self.assertEqual(result["status"], "unmatched")
        self.assertEqual(result["candidates"], [])

    def test_manufacturing_and_quality_are_not_silently_collapsed(self):
        result = route_instruction(
            "تولید کارخانه و کنترل کیفیت را بررسی کن",
            {"production-scheduling", "quality-inspector"},
        )
        self.assertEqual(result["status"], "ambiguous")
