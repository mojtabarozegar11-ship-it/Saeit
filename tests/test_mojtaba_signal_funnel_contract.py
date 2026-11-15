"""Commercial funnel contract for the single Mojtaba.bot.ai signal intake route."""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class MojtabaSignalFunnelContractTests(SimpleTestCase):
    def test_signal_desk_ctas_prefill_the_canonical_service(self):
        signal_page = (
            Path(settings.BASE_DIR) / "templates/moj-prop/signals/index.html"
        ).read_text(encoding="utf-8")
        self.assertGreaterEqual(
            signal_page.count('/moj-prop/?service=signals#request'), 2
        )

    def test_request_forms_accept_a_safe_service_query_prefill(self):
        for relative in ("templates/moj-prop-v4/index.html", "templates/moj-prop/index.html"):
            source = (Path(settings.BASE_DIR) / relative).read_text(encoding="utf-8")
            self.assertIn("new URLSearchParams(window.location.search)", source)
            self.assertIn("serviceSelect.value=requestedService", source)
            self.assertIn(
                "Object.prototype.hasOwnProperty.call(labels,requestedService)",
                source,
            )


class LegacySignalRootRealSubmissionTests(SimpleTestCase):
    """No buyer should mistake a local fake ID for a received sales request."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.html = (Path(settings.BASE_DIR) / "templates/moj-prop/index.html").read_text("utf-8")

    def test_submits_to_real_backend_and_requires_confirmed_201(self):
        self.assertIn("const endpoint='/moj-prop-intake/';", self.html)
        self.assertIn("method:'POST'", self.html)
        self.assertIn("response.status!==201", self.html)
        self.assertIn("body.request_id.startsWith('MOJPROP-')", self.html)
        self.assertIn("X-CSRFToken", self.html)
        self.assertIn("credentials:'same-origin'", self.html)

    def test_removes_local_phantom_order_ids_and_mailto_only_handoff(self):
        self.assertNotIn("localStorage.setItem('mojprop-last-request'", self.html)
        self.assertNotIn("Math.random().toString(36)", self.html)
        self.assertNotIn("mailto:", self.html)
        self.assertIn("Request NOT submitted.", self.html)

    def test_all_horizon_choices_match_actual_backend(self):
        for code in ("urgent", "week", "month", "review"):
            self.assertIn('<option value="'+code+'">', self.html)
        self.assertIn('id="website" name="website"', self.html)
        self.assertIn("consent:document.getElementById('consent').checked", self.html)

    def test_receipt_id_is_only_allocated_by_backend(self):
        self.assertIn("Request ID: '+(id||'not allocated')", self.html)
        self.assertIn("receipt=draft(data,'received for manual review',body.request_id)", self.html)
