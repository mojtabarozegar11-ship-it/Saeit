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
