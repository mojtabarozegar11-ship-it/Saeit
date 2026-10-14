"""Native ETH/TRX merchant wallet signatures: real cryptography, fake test keys.

Zero interaction with real wallet funds/keys. No live Django migrations, routes
or OpenAI tokens. ETH recovers EIP-191, TRX recovers TIP-191/base58check.
"""
import hashlib
import json
import secrets
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_keys import keys
from eth_utils import keccak

from mpw_native_checkout.models import MerchantWalletChallenge, MerchantWalletProof
from mpw_native_checkout.wallet_ownership import (
    MERCHANT_ADDRESSES, WalletOwnershipError, challenge_message,
    create_merchant_challenge, proven_assets, submit_merchant_proof,
    verify_merchant_signature,
)


def tron_base58_for_test(private_key):
    raw = b"\x41" + keccak(private_key.public_key.to_bytes())[-20:]
    data = raw + hashlib.sha256(hashlib.sha256(raw).digest()).digest()[:4]
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = int.from_bytes(data, "big")
    encoded = ""
    while n:
        n, remainder = divmod(n, 58)
        encoded = alphabet[remainder] + encoded
    return encoded


def tron_tip191_signature(private_key, message):
    payload = message.encode("utf-8")
    digest = keccak(b"\x19TRON Signed Message:\n" +
                    str(len(payload)).encode("ascii") + payload)
    raw = private_key.sign_msg_hash(digest).to_bytes()
    return "0x" + (raw[:64] + bytes([raw[64] + 27])).hex()


class MerchantWalletProofTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_superuser(
            username="merchant-proof-owner", email="owner@example.test",
            password="never-a-real-password",
        )
        self.stranger = User.objects.create_user(
            username="merchant-nonadmin", password="never-a-real-password",
        )
        self.eth = Account.create()
        self.tron_private = keys.PrivateKey(b"\x21" * 32)
        self.tron_address = tron_base58_for_test(self.tron_private)
        gate = override_settings(MPW_WALLET_PROOF_OWNER_ID=self.owner.pk)
        gate.enable()
        self.addCleanup(gate.disable)
        self.client.defaults["wsgi.url_scheme"] = "https"
        self.client.defaults["HTTP_HOST"] = "mojplaywin.com"

    def test_fake_ethereum_signer_controls_only_its_own_address(self):
        with patch.dict(MERCHANT_ADDRESSES, {"ETH":self.eth.address}):
            challenge, message = create_merchant_challenge(self.owner,"ETH")
            signature = Account.sign_message(
                encode_defunct(text=message),self.eth.key,
            ).signature.hex()
            self.assertTrue(verify_merchant_signature(
                "ETH",self.eth.address,message,signature,
            ))
            self.assertEqual(submit_merchant_proof(
                self.owner,challenge.pk,signature,
            ),"ETH")
            self.assertTrue(proven_assets()["ETH"])
        self.assertFalse(proven_assets()["ETH"]) # fixed configured receiver has no proof

    def test_ethereum_challenge_cannot_be_reused(self):
        with patch.dict(MERCHANT_ADDRESSES, {"ETH":self.eth.address}):
            challenge, msg = create_merchant_challenge(self.owner,"ETH")
            sig = "0x" + Account.sign_message(
                encode_defunct(text=msg),self.eth.key,
            ).signature.hex()
            submit_merchant_proof(self.owner,challenge.pk,sig)
            with self.assertRaises(WalletOwnershipError):
                submit_merchant_proof(self.owner,challenge.pk,sig)

    def test_tron_v2_signature_proves_base58_receiving_address(self):
        with patch.dict(MERCHANT_ADDRESSES, {"TRX":self.tron_address}):
            challenge,msg = create_merchant_challenge(self.owner,"TRX")
            signature=tron_tip191_signature(self.tron_private,msg)
            self.assertTrue(verify_merchant_signature(
                "TRX",self.tron_address,msg,signature))
            self.assertEqual(submit_merchant_proof(
                self.owner,challenge.pk,signature),"TRX")
            self.assertTrue(proven_assets()["TRX"])

    def test_tron_wrong_wallet_rejected_and_not_credited(self):
        with patch.dict(MERCHANT_ADDRESSES, {"TRX":self.tron_address}):
            challenge,msg = create_merchant_challenge(self.owner,"TRX")
            attacker = keys.PrivateKey(b"\x35"*32)
            with self.assertRaises(WalletOwnershipError):
                submit_merchant_proof(
                    self.owner,challenge.pk,tron_tip191_signature(attacker,msg),
                )
            self.assertFalse(MerchantWalletProof.objects.exists())
            challenge.refresh_from_db()
            self.assertEqual(challenge.failed_attempts,1)

    def test_old_challenge_invalidated_after_issuing_a_new_one(self):
        with patch.dict(MERCHANT_ADDRESSES, {"ETH":self.eth.address}):
            old,msg = create_merchant_challenge(self.owner,"ETH")
            new,_ = create_merchant_challenge(self.owner,"ETH")
            old.refresh_from_db()
            self.assertIsNotNone(old.used_at)
            with self.assertRaises(WalletOwnershipError):
                submit_merchant_proof(self.owner,old.pk,"0x"+"11"*65)
            self.assertIsNone(new.used_at)

    def test_expired_challenge_is_rejected(self):
        with patch.dict(MERCHANT_ADDRESSES, {"ETH":self.eth.address}):
            now=timezone.now()
            challenge,msg=create_merchant_challenge(self.owner,"ETH",now=now)
            sig=Account.sign_message(encode_defunct(text=msg),self.eth.key).signature.hex()
            with self.assertRaises(WalletOwnershipError):
                submit_merchant_proof(
                    self.owner,challenge.pk,sig,now=now+timedelta(minutes=6))
            self.assertFalse(MerchantWalletProof.objects.exists())

    def test_rate_limit_prevents_unlimited_nonce_generation(self):
        with patch.dict(MERCHANT_ADDRESSES, {"ETH":self.eth.address}):
            for _ in range(8):create_merchant_challenge(self.owner,"ETH")
            with self.assertRaises(WalletOwnershipError):
                create_merchant_challenge(self.owner,"TRX")

    def test_nonadmin_cannot_create_or_submit_challenge(self):
        with self.assertRaises(WalletOwnershipError):
            create_merchant_challenge(self.stranger,"ETH")
        with patch.dict(MERCHANT_ADDRESSES, {"ETH":self.eth.address}):
            challenge,_=create_merchant_challenge(self.owner,"ETH")
        with self.assertRaises(WalletOwnershipError):
            submit_merchant_proof(self.stranger,challenge.pk,"0x"+"22"*65)

    def test_no_customer_payment_state_is_changed_by_proof(self):
        with patch.dict(MERCHANT_ADDRESSES, {"ETH":self.eth.address}):
            challenge,msg=create_merchant_challenge(self.owner,"ETH")
            sig=Account.sign_message(encode_defunct(text=msg),self.eth.key).signature.hex()
            submit_merchant_proof(self.owner,challenge.pk,sig)
        self.assertEqual(MerchantWalletProof.objects.count(),1)
        from core.models import Order
        self.assertFalse(Order.objects.exists())

    def test_owner_page_is_private_and_not_public_checkout(self):
        page=reverse("mpw_wallet_proof:page")
        self.assertEqual(self.client.get(page).status_code,302)
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(page).status_code,403)
        self.client.force_login(self.owner)
        result=self.client.get(page,secure=True)
        self.assertEqual(result.status_code,200)
        self.assertContains(result,"هیچ پولی منتقل")
        self.assertContains(result,"TRON (TRX)")

    def test_post_challenge_uses_only_fixed_receiving_wallet(self):
        self.client.force_login(self.owner)
        with patch.dict(MERCHANT_ADDRESSES, {"ETH":self.eth.address}):
            response=self.client.post(reverse("mpw_wallet_proof:challenge"),
                data=json.dumps({"asset":"ETH"}),content_type="application/json",secure=True)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["address"],self.eth.address)
        self.assertIn("Nonce: ",response.json()["message"])
        self.assertFalse(response.json().get("checkout_activated",False))

    def test_another_superuser_cannot_access_selected_owner_page(self):
        another=get_user_model().objects.create_superuser(
            username="another-administrator",password="ci-only-password",
            email="other@example.test",
        )
        self.client.force_login(another)
        self.assertEqual(
            self.client.get(reverse("mpw_wallet_proof:page")).status_code,403
        )
        self.assertEqual(
            self.client.post(reverse("mpw_wallet_proof:challenge"),
                data='{"asset":"ETH"}',content_type="application/json",secure=True).status_code,
            403,
        )

    def test_superuser_denied_without_designated_owner_id(self):
        self.client.force_login(self.owner)
        with override_settings(MPW_WALLET_PROOF_OWNER_ID=None):
            self.assertEqual(
                self.client.get(reverse("mpw_wallet_proof:page")).status_code,403
            )

    def test_staff_non_superuser_cannot_issue_any_challenge(self):
        self.stranger.is_staff=True
        self.stranger.save(update_fields=["is_staff"])
        self.client.force_login(self.stranger)
        self.assertEqual(
            self.client.post(reverse("mpw_wallet_proof:challenge"),
                data='{"asset":"ETH"}',content_type="application/json",secure=True).status_code,403
        )

    def test_wrong_http_method_not_allowed(self):
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.get(reverse("mpw_wallet_proof:challenge")).status_code,405
        )

    def test_shared_django_other_domains_cannot_request_wallet_signatures(self):
        self.client.force_login(self.owner)
        response=self.client.post(
            reverse("mpw_wallet_proof:challenge"),
            data='{"asset":"ETH"}',content_type="application/json",
            secure=True, HTTP_HOST="zomorodmelal.ir",
        )
        self.assertEqual(response.status_code,403)
        self.assertFalse(MerchantWalletChallenge.objects.exists())

    def test_no_owner_signatures_can_be_issued_over_plain_http(self):
        self.client.force_login(self.owner)
        r=self.client.post(
            reverse("mpw_wallet_proof:challenge"),
            data='{"asset":"ETH"}',content_type="application/json",
            secure=False,
        )
        self.assertEqual(r.status_code,403)
        self.assertFalse(MerchantWalletChallenge.objects.exists())

    def test_csrf_required_even_when_authenticated(self):
        c=Client(enforce_csrf_checks=True)
        c.defaults["wsgi.url_scheme"] = "https"
        c.defaults["HTTP_HOST"] = "mojplaywin.com"
        c.force_login(self.owner)
        response=c.post(reverse("mpw_wallet_proof:challenge"),
                 data='{"asset":"ETH"}',content_type="application/json",secure=True)
        self.assertEqual(response.status_code,403)
