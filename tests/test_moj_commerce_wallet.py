"""Crypto challenge ownership proof and replay controls using test-only keys."""
import hashlib
import json
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from eth_keys import keys
from eth_utils import keccak
from moj_commerce.models import Merchant, MerchantAddress, WalletOwnershipChallenge
from moj_commerce.wallet_proof import issue_wallet_challenge, complete_wallet_challenge, recover_signer_tron_hex
from moj_commerce.services import CommerceRejected

ALPHABET='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'


def test_wallet_address(privkey):
    body=bytes.fromhex('41')+privkey.public_key.to_canonical_address()
    checksum=hashlib.sha256(hashlib.sha256(body).digest()).digest()[:4]
    i=int.from_bytes(body+checksum,'big'); out=''
    while i:
        i,d=divmod(i,58);out=ALPHABET[d]+out
    return out


def sign_v2(private_key,message):
    encoded=message.encode('utf8')
    digest=keccak(b'\x19TRON Signed Message:\n'+str(len(encoded)).encode('ascii')+encoded)
    raw=private_key.sign_msg_hash(digest).to_bytes()
    return '0x'+(raw[:64]+bytes([raw[-1]+27])).hex()


class WalletOwnershipTests(TestCase):
    def setUp(self):
        User=get_user_model()
        self.owner=User.objects.create_user('wallet-owner')
        self.attacker=User.objects.create_user('wallet-attacker')
        self.merchant=Merchant.objects.create(owner=self.owner,name='Pilot merchant',status='pending')
        self.priv=keys.PrivateKey(bytes.fromhex('00'*31+'01'))  # TEST ONLY, never a seller key
        self.otherpriv=keys.PrivateKey(bytes.fromhex('00'*31+'02'))
        self.address=MerchantAddress.objects.create(merchant=self.merchant,address=test_wallet_address(self.priv))

    def issue(self):
        return issue_wallet_challenge(self.merchant.public_id,self.address.id,self.owner.id)

    def complete(self,c,signature):
        return complete_wallet_challenge(self.merchant.public_id,self.address.id,self.owner.id,
                                         c['challenge_id'],signature)

    def test_wallet_v2_signature_recovers_real_tron_address(self):
        c=self.issue()
        signature=sign_v2(self.priv,c['message'])
        recovered=recover_signer_tron_hex(c['message'],signature)
        self.assertEqual(recovered,'41'+self.priv.public_key.to_canonical_address().hex().upper())
        self.assertEqual(self.complete(c,signature)['status'],'verified')
        self.address.refresh_from_db()
        self.assertEqual(self.address.verified_via,'tron-sign-v2')
        self.assertIsNotNone(self.address.verified_at)

    def test_wrong_wallet_signature_consumes_nonce(self):
        c=self.issue()
        with self.assertRaises(CommerceRejected): self.complete(c,sign_v2(self.otherpriv,c['message']))
        self.assertIsNotNone(WalletOwnershipChallenge.objects.get(address=self.address).consumed_at)
        with self.assertRaises(CommerceRejected): self.complete(c,sign_v2(self.priv,c['message']))
        self.address.refresh_from_db();self.assertIsNone(self.address.verified_at)

    def test_one_time_signature_cannot_replay(self):
        c=self.issue();sig=sign_v2(self.priv,c['message']);self.complete(c,sig)
        with self.assertRaises(CommerceRejected): self.complete(c,sig)

    def test_old_nonce_rejected_on_reissue(self):
        c=self.issue()
        WalletOwnershipChallenge.objects.filter(address=self.address).update(created_at=timezone.now()-timedelta(minutes=2))
        replacement=self.issue()
        self.assertNotEqual(c['challenge_id'],replacement['challenge_id'])
        with self.assertRaises(CommerceRejected): self.complete(c,sign_v2(self.priv,c['message']))
        self.complete(replacement,sign_v2(self.priv,replacement['message']))

    def test_new_challenge_cooldown_enforced(self):
        self.issue()
        with self.assertRaisesRegex(CommerceRejected,'cooldown'):
            self.issue()

    def test_expired_challenge_rejected(self):
        c=self.issue()
        WalletOwnershipChallenge.objects.filter(address=self.address).update(expires_at=timezone.now()-timedelta(seconds=1))
        with self.assertRaises(CommerceRejected):self.complete(c,sign_v2(self.priv,c['message']))

    def test_changed_message_never_verifies(self):
        c=self.issue()
        with self.assertRaises(CommerceRejected): self.complete(c,sign_v2(self.priv,c['message']+'FAKE'))
        self.address.refresh_from_db();self.assertIsNone(self.address.verified_at)

    def test_invalid_signature_encoding_consumed(self):
        c=self.issue()
        with self.assertRaises(CommerceRejected):self.complete(c,'garbage')
        self.assertIsNotNone(WalletOwnershipChallenge.objects.get(address=self.address).consumed_at)

    def test_attacker_cannot_issue_or_redeem_another_sellers_challenge(self):
        with self.assertRaises(CommerceRejected):issue_wallet_challenge(self.merchant.public_id,self.address.id,self.attacker.id)
        c=self.issue()
        with self.assertRaises(CommerceRejected): complete_wallet_challenge(
            self.merchant.public_id,self.address.id,self.attacker.id,c['challenge_id'],sign_v2(self.priv,c['message']))
        self.complete(c,sign_v2(self.priv,c['message']))

    def test_suspended_merchant_refused(self):
        self.merchant.status='suspended';self.merchant.save(update_fields=['status'])
        with self.assertRaises(CommerceRejected):self.issue()

    def test_address_checksum_must_be_real(self):
        self.address.address='T'+'A'*33
        self.address.save(update_fields=['address'])
        with self.assertRaises(CommerceRejected):self.issue()

    def test_wallet_api_issue_and_verify_authenticated(self):
        self.client.force_login(self.owner)
        url=reverse('moj-commerce-wallet-challenge',args=[self.merchant.public_id,self.address.id])
        response=self.client.post(url)
        self.assertEqual(response.status_code,201,response.content)
        payload=response.json()
        verify=reverse('moj-commerce-wallet-verify',args=[self.merchant.public_id,self.address.id])
        proof=self.client.post(verify,data=json.dumps({'challenge_id':payload['challenge_id'],
            'signature':sign_v2(self.priv,payload['message'])}),content_type='application/json')
        self.assertEqual(proof.status_code,200,proof.content)
        self.assertEqual(proof.json()['method'],'tron-sign-v2')
        self.assertEqual(proof['Cache-Control'],'no-store, private')

    def test_wallet_api_requires_same_owner(self):
        self.client.force_login(self.attacker)
        url=reverse('moj-commerce-wallet-challenge',args=[self.merchant.public_id,self.address.id])
        self.assertEqual(self.client.post(url).status_code,409)

    def test_wallet_api_rejects_duplicate_json_fields(self):
        self.client.force_login(self.owner)
        c=self.issue()
        url=reverse('moj-commerce-wallet-verify',args=[self.merchant.public_id,self.address.id])
        body=('{'+'"challenge_id":"'+c['challenge_id']+'","challenge_id":"'+c['challenge_id']+'","signature":"x"}')
        self.assertEqual(self.client.post(url,data=body,content_type='application/json').status_code,400)

    @override_settings(MOJ_COMMERCE_REQUIRE_SIGNED_WALLET=True)
    def test_unsigned_manual_address_does_not_qualify_for_payment(self):
        from decimal import Decimal
        from moj_commerce.models import DigitalProduct,Purchase
        from moj_commerce.services import _validate_existing_purchase
        buyer=self.attacker
        self.merchant.status='approved';self.merchant.save(update_fields=['status'])
        self.address.verified_at=timezone.now();self.address.save(update_fields=['verified_at'])
        product=DigitalProduct.objects.create(merchant=self.merchant,sku='ZIP1',title='T',
            price_usd=Decimal('4.00'),file_key='a'*32,sha256='b'*64,active=True)
        p=Purchase.objects.create(reference='MOJC-wallet-confirm-1',merchant=self.merchant,
            product=product,buyer=buyer,destination=self.address,usd_amount=Decimal('4.00'),
            amount_sun=12000000,expires_at=timezone.now()+timedelta(minutes=5))
        with self.assertRaisesRegex(CommerceRejected,'prove control'):_validate_existing_purchase(p)
        c=self.issue();self.complete(c,sign_v2(self.priv,c['message']))
        p.destination.refresh_from_db()
        _validate_existing_purchase(p)