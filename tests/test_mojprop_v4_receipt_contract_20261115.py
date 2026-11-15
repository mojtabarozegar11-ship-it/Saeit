"""The public Moj Prop v4 form may show success only for a backend receipt."""
from pathlib import Path
from django.conf import settings
from django.test import SimpleTestCase


class MojPropV4ReceiptContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.html = (
            Path(settings.BASE_DIR) / "templates/moj-prop-v4/index.html"
        ).read_text(encoding="utf-8")

    def test_success_requires_created_response_and_backend_id_shape(self):
        self.assertIn("response.status!==201", self.html)
        self.assertIn("data.ok!==true", self.html)
        self.assertIn(
            "!/^MOJPROP-[0-9]{8}-[A-F0-9]{8}$/.test(data.request_id)",
            self.html,
        )
        self.assertIn("typeof data.request_id!=='string'", self.html)

    def test_failed_submission_cannot_create_a_local_receipt(self):
        self.assertIn("receipt='';", self.html)
        self.assertIn("Request NOT submitted.", self.html)
        self.assertNotIn(
            "not submitted; local draft only",
            self.html,
        )

    def test_receipt_is_only_built_after_strict_success_gate(self):
        gate = "if(response.status!==201 || data.ok!==true"
        draft = "receipt=draft(name,email,service,horizon,notes,'received for manual review',data.request_id);"
        self.assertLess(self.html.index(gate), self.html.index(draft))
