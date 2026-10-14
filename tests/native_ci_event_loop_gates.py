"""Future release command stays disabled and coin-specific. All services mocked."""
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

SECRET=b"staging-unit-test-secret-never-use-for-mainnet-"*2


class NativeEventLoopReleaseGateTests(SimpleTestCase):
    def test_all_live_flags_default_off(self):
        with override_settings(
            MPW_NATIVE_EVENT_ENABLED=False,
            MPW_NATIVE_AUTOPAY_ENABLED=False,
            MPW_NATIVE_RELEASE_APPROVED=False,
        ), patch("mpw_native_checkout.management.commands.mpw_native_event_loop.proven_assets",
                     return_value={"ETH":True,"TRX":True}), patch(
                "mpw_native_checkout.management.commands.mpw_native_event_loop.run_local_worker") as runner:
            with self.assertRaises(CommandError):
                call_command("mpw_native_event_loop")
            runner.assert_not_called()

    @override_settings(
        MPW_NATIVE_EVENT_ENABLED=True,
        MPW_NATIVE_AUTOPAY_ENABLED=True,
        MPW_NATIVE_RELEASE_APPROVED=False,
    )
    def test_not_allowed_to_run_with_release_not_approved(self):
        with patch("mpw_native_checkout.management.commands.mpw_native_event_loop.reconcile_once") as settle:
            with self.assertRaises(CommandError):
                call_command("mpw_native_event_loop")
            settle.assert_not_called()

    def test_wrong_private_secret_permissions_block_worker(self):
        with tempfile.TemporaryDirectory() as path:
            root=Path(path)
            key=root/"secret"
            key.write_bytes(SECRET)
            key.chmod(0o644)
            with override_settings(
                MPW_NATIVE_EVENT_ENABLED=True,
                MPW_NATIVE_AUTOPAY_ENABLED=True,
                MPW_NATIVE_RELEASE_APPROVED=True,
                MPW_NATIVE_MERCHANT_PROOFS={"ETH":True,"TRX":True},
                MPW_NATIVE_EVENT_HOME=str(root),
                MPW_NATIVE_EVENT_SECRET_FILE=str(key),
            ), patch(
                "mpw_native_checkout.management.commands.mpw_native_event_loop.proven_assets",
                return_value={"ETH":True,"TRX":True},
            ), patch(
                "mpw_native_checkout.management.commands.mpw_native_event_loop.run_local_worker"
            ) as runner:
                with self.assertRaises(CommandError):
                    call_command("mpw_native_event_loop")
                runner.assert_not_called()

    def test_future_approved_event_only_scans_selected_coin(self):
        with tempfile.TemporaryDirectory() as path:
            root=Path(path)
            key=root/"secret"
            key.write_bytes(SECRET)
            key.chmod(0o600)
            observed=[]
            def fake_loop(home,private_key,**kwargs):
                self.assertEqual(home,str(root))
                self.assertEqual(private_key,SECRET)
                # Deliberately select ETH once and TRX once.
                observed.extend(kwargs["eth_scan"]())
                observed.extend(kwargs["trx_scan"]())
            with override_settings(
                MPW_NATIVE_EVENT_ENABLED=True,
                MPW_NATIVE_AUTOPAY_ENABLED=True,
                MPW_NATIVE_RELEASE_APPROVED=True,
                MPW_NATIVE_MERCHANT_PROOFS={"ETH":True,"TRX":True},
                MPW_NATIVE_EVENT_HOME=str(root),
                MPW_NATIVE_EVENT_SECRET_FILE=str(key),
            ), patch("mpw_native_checkout.management.commands.mpw_native_event_loop.proven_assets",
                     return_value={"ETH":True,"TRX":True}), patch(
                "mpw_native_checkout.management.commands.mpw_native_event_loop.run_local_worker",side_effect=fake_loop), patch(
                "mpw_native_checkout.management.commands.mpw_native_event_loop.reconcile_once",
                side_effect=lambda asset_filter: {"matched":1 if asset_filter=="ETH" else 0},
            ) as reconcile:
                call_command("mpw_native_event_loop")
            self.assertEqual(observed,[None])
            self.assertEqual([x.kwargs for x in reconcile.call_args_list],[
                {"asset_filter":"ETH"},{"asset_filter":"TRX"},
            ])

    def test_fake_settings_cannot_replace_signed_wallet_proofs(self):
        with tempfile.TemporaryDirectory() as path:
            root=Path(path)
            key=root/"secret"
            key.write_bytes(SECRET)
            key.chmod(0o600)
            with override_settings(
                MPW_NATIVE_EVENT_ENABLED=True,
                MPW_NATIVE_AUTOPAY_ENABLED=True,
                MPW_NATIVE_RELEASE_APPROVED=True,
                MPW_NATIVE_MERCHANT_PROOFS={"ETH":True,"TRX":True},
                MPW_NATIVE_EVENT_HOME=str(root),
                MPW_NATIVE_EVENT_SECRET_FILE=str(key),
            ), patch(
                "mpw_native_checkout.management.commands.mpw_native_event_loop.proven_assets",
                return_value={"ETH":False,"TRX":False},
            ), patch(
                "mpw_native_checkout.management.commands.mpw_native_event_loop.run_local_worker"
            ) as runner:
                with self.assertRaises(CommandError):
                    call_command("mpw_native_event_loop")
                runner.assert_not_called()
