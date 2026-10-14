"""Inactive Django purchase-event integration tests; no HTTP calls or payment activity."""
from datetime import timedelta
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from mpw_native_checkout.purchase_notify import (
    send_invoice_event, NotificationUnavailable,
)
from mpw_native_checkout.signals import on_native_invoice_change
from mpw_native_checkout.models import NativeInvoice
from scripts.mojplaywin_purchase_events import verify_event

KEY="demo-not-real-HMAC-key-"*3
URL="https://vps.example.com/api/mpw/native-watch-event"


class EventNotificationTests(TestCase):
    def invoice(self):
        return SimpleNamespace(
            pk=10, order_id=70, asset="ETH",
            expires_at=timezone.now() + timedelta(minutes=9),
            product_id=72, status="awaiting",
            sender_signature_verified_at=timezone.now(),
            merchant_ownership_verified_at=timezone.now(),
        )

    def test_reuses_private_0600_secret_file_without_environment_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            secret_path = Path(directory) / "secret"
            secret_path.write_text(KEY, encoding="utf-8")
            secret_path.chmod(0o600)
            with override_settings(
                MPW_NATIVE_EVENT_ENABLED=True,
                MPW_NATIVE_EVENT_TRANSPORT="unix",
                MPW_NATIVE_EVENT_SOCKET="/tmp/mpw-ci-only.sock",
                MPW_NATIVE_EVENT_SECRET_FILE=str(secret_path),
                MPW_NATIVE_EVENT_SECRET="",
            ), patch(
                "scripts.mojplaywin_cpanel_local_event_worker.socket_request",
                return_value="delivered",
            ) as deliver:
                self.assertEqual(
                    send_invoice_event(self.invoice(), action="invoice_open"),
                    "delivered",
                )
            event = verify_event(
                deliver.call_args.args[1], deliver.call_args.args[2],
                KEY.encode("utf-8"),
            )
            self.assertEqual(event["order"], 70)

    def test_insecure_key_file_is_rejected_without_emitting_message(self):
        with tempfile.TemporaryDirectory() as directory:
            secret_path = Path(directory) / "secret"
            secret_path.write_text(KEY, encoding="utf-8")
            secret_path.chmod(0o644)
            with override_settings(
                MPW_NATIVE_EVENT_ENABLED=True,
                MPW_NATIVE_EVENT_TRANSPORT="unix",
                MPW_NATIVE_EVENT_SOCKET="/tmp/mpw-ci-only.sock",
                MPW_NATIVE_EVENT_SECRET_FILE=str(secret_path),
                MPW_NATIVE_EVENT_SECRET=KEY,
            ), patch(
                "scripts.mojplaywin_cpanel_local_event_worker.socket_request"
            ) as deliver:
                with self.assertRaises(NotificationUnavailable):
                    send_invoice_event(self.invoice(), action="invoice_open")
                deliver.assert_not_called()

    def test_symlinked_event_key_is_rejected_without_emitting_message(self):
        with tempfile.TemporaryDirectory() as directory:
            secret_path = Path(directory) / "secret"
            secret_path.write_text(KEY, encoding="utf-8")
            secret_path.chmod(0o600)
            linked_key = Path(directory) / "linked-secret"
            linked_key.symlink_to(secret_path)
            with override_settings(
                MPW_NATIVE_EVENT_ENABLED=True,
                MPW_NATIVE_EVENT_TRANSPORT="unix",
                MPW_NATIVE_EVENT_SOCKET="/tmp/mpw-ci-only.sock",
                MPW_NATIVE_EVENT_SECRET_FILE=str(linked_key),
            ), patch(
                "scripts.mojplaywin_cpanel_local_event_worker.socket_request"
            ) as deliver:
                with self.assertRaises(NotificationUnavailable):
                    send_invoice_event(self.invoice(), action="invoice_open")
                deliver.assert_not_called()

    @override_settings(MPW_NATIVE_EVENT_ENABLED=True,
                       MPW_NATIVE_EVENT_TRANSPORT="unix",
                       MPW_NATIVE_EVENT_SOCKET="/tmp/mpw-ci-only.sock",
                       MPW_NATIVE_EVENT_SECRET=KEY)
    def test_same_host_invoice_triggers_authenticated_unix_message(self):
        invoice=self.invoice()
        with patch("scripts.mojplaywin_cpanel_local_event_worker.socket_request",
                   return_value="delivered") as deliver:
            result=send_invoice_event(invoice,action="invoice_open")
        self.assertEqual(result,"delivered")
        self.assertEqual(deliver.call_args.args[0],"/tmp/mpw-ci-only.sock")
        body,signature=deliver.call_args.args[1:3]
        event=verify_event(body,signature,KEY.encode())
        self.assertEqual(event["invoice"],10)
        self.assertEqual(event["order"],70)
        self.assertEqual(event["asset"],"ETH")

    @override_settings(MPW_NATIVE_EVENT_ENABLED=True,
                       MPW_NATIVE_EVENT_TRANSPORT="unix",
                       MPW_NATIVE_EVENT_SOCKET="/tmp/mpw-ci-only.sock",
                       MPW_NATIVE_EVENT_SECRET="")
    def test_missing_unix_signing_key_never_dispatches(self):
        with patch("scripts.mojplaywin_cpanel_local_event_worker.socket_request") as deliver:
            with self.assertRaises(NotificationUnavailable):
                send_invoice_event(self.invoice(),action="invoice_open")
        deliver.assert_not_called()

    def test_default_disabled_has_zero_http_calls(self):
        with override_settings(MPW_NATIVE_EVENT_ENABLED=False):
            with patch("mpw_native_checkout.purchase_notify.urlopen") as send:
                self.assertEqual(send_invoice_event(self.invoice(),action="invoice_open"),"disabled")
                send.assert_not_called()

    @override_settings(MPW_NATIVE_EVENT_ENABLED=True,
                       MPW_NATIVE_EVENT_URL=URL,
                       MPW_NATIVE_EVENT_HOST="vps.example.com",
                       MPW_NATIVE_EVENT_SECRET=KEY)
    def test_signed_purchase_message_contains_only_ids_and_coin(self):
        calls=[]
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,size):return b"ok"
        def fake_opener(req,timeout):
            self.assertEqual(timeout,3)
            body=req.data
            signature=req.headers.get("X-mpw-signature")
            if signature is None:
                signature=req.headers.get("X-Mpw-Signature")
            calls.append(verify_event(body,signature,KEY.encode()))
            return Response()
        result=send_invoice_event(self.invoice(),action="invoice_open",opener=fake_opener)
        self.assertEqual(result,"delivered")
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0]["invoice"],10)
        self.assertEqual(calls[0]["asset"],"ETH")
        self.assertNotIn("email",calls[0])

    @override_settings(MPW_NATIVE_EVENT_ENABLED=True,
                       MPW_NATIVE_EVENT_URL="http://localhost:8876/api/mpw/native-watch-event",
                       MPW_NATIVE_EVENT_HOST="localhost",
                       MPW_NATIVE_EVENT_SECRET=KEY)
    def test_public_plaintext_http_rejected(self):
        with self.assertRaises(NotificationUnavailable):
            send_invoice_event(self.invoice(),action="invoice_open")

    @override_settings(MPW_NATIVE_EVENT_ENABLED=True,
                       MPW_NATIVE_EVENT_URL="https://evil.example.com/api/mpw/native-watch-event",
                       MPW_NATIVE_EVENT_HOST="vps.example.com",
                       MPW_NATIVE_EVENT_SECRET=KEY)
    def test_unapproved_host_rejected(self):
        with self.assertRaises(NotificationUnavailable):
            send_invoice_event(self.invoice(),action="invoice_open")

    def test_created_verified_invoice_triggers_once(self):
        inv=self.invoice()
        with patch("mpw_native_checkout.signals.notify_after_commit") as notify:
            on_native_invoice_change(NativeInvoice,inv,created=True)
            notify.assert_called_once_with(inv,"invoice_open")

    def test_created_unverified_invoice_does_not_trigger(self):
        inv=self.invoice()
        inv.merchant_ownership_verified_at=None
        with patch("mpw_native_checkout.signals.notify_after_commit") as notify:
            on_native_invoice_change(NativeInvoice,inv,created=True)
            notify.assert_not_called()

    def test_paid_invoice_sends_stop(self):
        inv=self.invoice()
        inv.status="paid"
        with patch("mpw_native_checkout.signals.notify_after_commit") as notify:
            on_native_invoice_change(NativeInvoice,inv,created=False,update_fields={"status"})
            notify.assert_called_once_with(inv,"invoice_closed")

    def test_unrelated_update_does_not_notify(self):
        inv=self.invoice()
        inv.status="awaiting"
        with patch("mpw_native_checkout.signals.notify_after_commit") as notify:
            on_native_invoice_change(NativeInvoice,inv,created=False,update_fields={"amount_atomic"})
            notify.assert_not_called()
