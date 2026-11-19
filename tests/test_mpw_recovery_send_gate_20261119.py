import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class MojPlayWinRecoverySendGateTest(unittest.TestCase):
    def read(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_settings_default_outbound_mail_gate_is_false(self):
        settings = self.read("config/settings.py")
        self.assertIn(
            'MPW_GUEST_EMAIL_SEND_APPROVED = env.bool("MPW_GUEST_EMAIL_SEND_APPROVED", default=False)',
            settings,
        )

    def test_send_boundary_requires_third_gate(self):
        service = self.read("services/mpw_trx_email_recovery.py")
        self.assertIn("def _email_send_enabled():", service)
        self.assertIn(
            'getattr(settings, "MPW_GUEST_EMAIL_SEND_APPROVED", False) is True',
            service,
        )
        self.assertIn('LOG.info("mpw_recovery_email_send_blocked")', service)

    def test_route_does_not_promise_recovery_when_send_is_off(self):
        service = self.read("services/mpw_trx_email_recovery.py")
        self.assertIn("if not _email_send_enabled():", service)
