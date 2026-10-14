"""Release requires verified deployment readiness, not merchant purchase approval.

Tests are isolated and never call blockchain RPC or use real receiving keys.
"""
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

SECRET = b"staging-unit-test-secret-never-use-for-mainnet-" * 2


class NativeEventLoopReleaseGateTests(SimpleTestCase):
    def test_all_live_flags_default_off(self):
        with override_settings(
            MPW_NATIVE_EVENT_ENABLED=False,
            MPW_NATIVE_AUTOPAY_ENABLED=False,
            MPW_NATIVE_RELEASE_APPROVED=False,
        ), patch(
            "mpw_native_checkout.management.commands.mpw_native_event_loop.run_local_worker"
        ) as runner:
            with self.assertRaises(CommandError):
                call_command("mpw_native_event_loop")
            runner.assert_not_called()

    @override_settings(
        MPW_NATIVE_EVENT_ENABLED=True,
        MPW_NATIVE_AUTOPAY_ENABLED=True,
        MPW_NATIVE_RELEASE_APPROVED=False,
    )
    def test_no_release_means_no_worker_even_without_merchant_approval(self):
        with patch(
            "mpw_native_checkout.management.commands.mpw_native_event_loop.reconcile_once"
        ) as settle:
            with self.assertRaises(CommandError):
                call_command("mpw_native_event_loop")
            settle.assert_not_called()

    def test_unsafe_private_event_signing_key_always_blocks(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            key = root / "secret"
            key.write_bytes(SECRET)
            key.chmod(0o644)
            with override_settings(
                MPW_NATIVE_EVENT_ENABLED=True,
                MPW_NATIVE_AUTOPAY_ENABLED=True,
                MPW_NATIVE_RELEASE_APPROVED=True,
                MPW_NATIVE_EVENT_HOME=str(root),
                MPW_NATIVE_EVENT_SECRET_FILE=str(key),
            ), patch(
                "mpw_native_checkout.management.commands.mpw_native_event_loop.run_local_worker"
            ) as runner:
                with self.assertRaises(CommandError):
                    call_command("mpw_native_event_loop")
                runner.assert_not_called()

    def test_approved_worker_has_zero_merchant_signature_dependency(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            key = root / "secret"
            key.write_bytes(SECRET)
            key.chmod(0o600)
            observed = []

            def fake_loop(home, private_key, **kwargs):
                self.assertEqual(home, str(root))
                self.assertEqual(private_key, SECRET)
                # Simulate authenticated event for only the purchased asset.
                observed.extend(kwargs["eth_scan"]())

            with override_settings(
                MPW_NATIVE_EVENT_ENABLED=True,
                MPW_NATIVE_AUTOPAY_ENABLED=True,
                MPW_NATIVE_RELEASE_APPROVED=True,
                MPW_NATIVE_MERCHANT_PROOFS={},  # intentionally no owner proof
                MPW_NATIVE_EVENT_HOME=str(root),
                MPW_NATIVE_EVENT_SECRET_FILE=str(key),
            ), patch(
                "mpw_native_checkout.management.commands.mpw_native_event_loop.run_local_worker",
                side_effect=fake_loop,
            ), patch(
                "mpw_native_checkout.management.commands.mpw_native_event_loop.reconcile_once",
                return_value={"matched": 1},
            ) as reconcile:
                call_command("mpw_native_event_loop")
            self.assertEqual(observed, [None])
            reconcile.assert_called_once_with(asset_filter="ETH")

    def test_missing_event_secret_blocks_all_sales_automation(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            with override_settings(
                MPW_NATIVE_EVENT_ENABLED=True,
                MPW_NATIVE_AUTOPAY_ENABLED=True,
                MPW_NATIVE_RELEASE_APPROVED=True,
                MPW_NATIVE_EVENT_HOME=str(root),
                MPW_NATIVE_EVENT_SECRET_FILE=str(root / "missing"),
            ), patch(
                "mpw_native_checkout.management.commands.mpw_native_event_loop.run_local_worker"
            ) as runner:
                with self.assertRaises(CommandError):
                    call_command("mpw_native_event_loop")
                runner.assert_not_called()
