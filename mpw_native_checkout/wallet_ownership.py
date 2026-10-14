"""Cryptographic proof that merchant controls fixed receiving wallets.

STAGING ONLY. No private keys, transfers, or gas.
ETH: EIP-191 personal_sign; TRX: TRON TIP-191 signMessageV2.
Signatures are verified on the server against one-time admin challenges.
Screenshots and client booleans cannot prove ownership.
"""
import hashlib
import re
import secrets
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from scripts.mojplaywin_native_chain_verify import tron_address_to_hex, VerificationError
from .models import MerchantWalletChallenge, MerchantWalletProof

MERCHANT_ADDRESSES = {
    "ETH": "0x89149b01f59115B86553561F12438D2ADF517E75",
    "TRX": "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73",
}
CHAIN_NAMES = {"ETH": "Ethereum mainnet", "TRX": "TRON mainnet"}
MAX_AGE_SECONDS = 300
ISSUE_LIMIT_PER_TEN_MINUTES = 8
SIGNATURE_SCHEMES = {"ETH": "EIP-191-personal_sign", "TRX": "TRON-TIP-191-signMessageV2"}


class WalletOwnershipError(ValueError):
    pass


def _require_owner(owner):
    if (not getattr(owner, "is_authenticated", False)
            or not getattr(owner, "is_active", False)
            or not getattr(owner, "is_superuser", False)
            or not isinstance(owner.pk, int)):
        raise WalletOwnershipError("Owner administrator required")


def _recipient(asset):
    if type(asset) is not str or asset not in MERCHANT_ADDRESSES:
        raise WalletOwnershipError("Unsupported wallet asset")
    address = MERCHANT_ADDRESSES[asset]
    if asset == "ETH":
        if not re.fullmatch(r"0x[0-9a-fA-F]{40}", address):
            raise WalletOwnershipError("Configured Ethereum receiver is invalid")
    else:
        try:
            tron_address_to_hex(address)
        except VerificationError as exc:
            raise WalletOwnershipError("Configured TRON receiver is invalid") from exc
    return address


def challenge_message(challenge):
    """Canonical ASCII message, reproduced server-side rather than browser-supplied."""
    address = _recipient(challenge.asset)
    if address.lower() != challenge.address.lower():
        raise WalletOwnershipError("Recipient changed since challenge issuance")
    return "\n".join((
        "MojPlayWin Merchant Wallet Ownership",
        "Domain: mojplaywin.com",
        "Action: Verify receiving-wallet control ONLY",
        "No token transfer, withdrawal, or spending approval is requested.",
        "Network: " + CHAIN_NAMES[challenge.asset],
        "Address: " + challenge.address,
        "Admin user ID: " + str(challenge.owner_id),
        "Challenge ID: " + str(challenge.pk),
        "Nonce: " + challenge.nonce,
        "Issued (UTC epoch): " + str(int(challenge.issued_at.timestamp())),
        "Expires (UTC epoch): " + str(int(challenge.expires_at.timestamp())),
    ))


def create_merchant_challenge(owner, asset, *, now=None):
    _require_owner(owner)
    address = _recipient(asset)
    now = now or timezone.now()
    with transaction.atomic():
        recent = MerchantWalletChallenge.objects.filter(
            owner=owner, issued_at__gte=now - timedelta(minutes=10)
        ).count()
        if recent >= ISSUE_LIMIT_PER_TEN_MINUTES:
            raise WalletOwnershipError("Challenge creation rate limit reached")
        MerchantWalletChallenge.objects.filter(
            owner=owner, asset=asset, used_at__isnull=True,
        ).update(used_at=now)
        challenge = MerchantWalletChallenge.objects.create(
            asset=asset, address=address, owner=owner,
            nonce=secrets.token_hex(32), issued_at=now,
            expires_at=now + timedelta(seconds=MAX_AGE_SECONDS),
        )
    return challenge, challenge_message(challenge)


def _signature_bytes(signature):
    if not isinstance(signature, str) or not re.fullmatch(
        r"(?:0x)?[0-9a-fA-F]{130}", signature,
    ):
        raise WalletOwnershipError("Wallet signature must contain 65 bytes")
    raw = bytes.fromhex(signature[2:] if signature.startswith("0x") else signature)
    if raw[-1] not in (0, 1, 27, 28):
        raise WalletOwnershipError("Unsupported signature recovery ID")
    return raw


def verify_merchant_signature(asset, address, message, signature):
    expected = _recipient(asset)
    if address.lower() != expected.lower():
        raise WalletOwnershipError("Unexpected configured wallet")
    raw = _signature_bytes(signature)
    if not isinstance(message, str) or not (60 <= len(message) <= 1000):
        raise WalletOwnershipError("Invalid challenge message")
    if asset == "ETH":
        try:
            from eth_account import Account
            from eth_account.messages import encode_defunct
            signer = Account.recover_message(
                encode_defunct(text=message), signature=raw,
            )
        except (ImportError, ValueError, TypeError, AssertionError) as exc:
            raise WalletOwnershipError("Ethereum signature invalid") from exc
        return signer.lower() == expected.lower()
    if asset == "TRX":
        try:
            from eth_keys import keys
            from eth_utils import keccak
            recovery = raw[-1] - 27 if raw[-1] >= 27 else raw[-1]
            sig = keys.Signature(signature_bytes=raw[:64] + bytes([recovery]))
            payload = message.encode("utf-8")
            digest = keccak(
                b"\x19TRON Signed Message:\n" +
                str(len(payload)).encode("ascii") + payload
            )
            public_key = sig.recover_public_key_from_msg_hash(digest)
            recovered = "41" + keccak(public_key.to_bytes())[-20:].hex()
            return recovered.lower() == tron_address_to_hex(expected).lower()
        except (ImportError, ValueError, TypeError, AssertionError, VerificationError) as exc:
            raise WalletOwnershipError("TRON signature invalid") from exc
    raise WalletOwnershipError("Unsupported wallet asset")


def submit_merchant_proof(owner, challenge_id, signature, *, now=None):
    """One-use row lock and audited signed proof; never mutate paid status."""
    _require_owner(owner)
    if type(challenge_id) is not int or challenge_id <= 0:
        raise WalletOwnershipError("Invalid challenge identity")
    now = now or timezone.now()
    failure = None
    with transaction.atomic():
        challenge = MerchantWalletChallenge.objects.select_for_update().filter(
            pk=challenge_id, owner=owner,
        ).first()
        if challenge is None or challenge.used_at is not None:
            raise WalletOwnershipError("Challenge missing or already used")
        if now < challenge.issued_at or now >= challenge.expires_at:
            raise WalletOwnershipError("Challenge expired")
        if challenge.failed_attempts >= 4:
            raise WalletOwnershipError("Challenge locked")
        message = challenge_message(challenge)
        try:
            valid = verify_merchant_signature(
                challenge.asset, challenge.address, message, signature,
            )
        except WalletOwnershipError:
            valid = False
        if not valid:
            challenge.failed_attempts += 1
            if challenge.failed_attempts >= 4:
                challenge.used_at = now
                challenge.save(update_fields=["failed_attempts", "used_at"])
            else:
                challenge.save(update_fields=["failed_attempts"])
            failure = "Signature does not match configured receiving wallet"
        else:
            challenge.used_at = now
            challenge.verified_at = now
            challenge.save(update_fields=["used_at", "verified_at"])
            MerchantWalletProof.objects.update_or_create(
                asset=challenge.asset,
                defaults={
                    "address": challenge.address, "owner": owner,
                    "challenge": challenge, "verified_at": now,
                    "signature_scheme": SIGNATURE_SCHEMES[challenge.asset],
                    "signature_sha256": hashlib.sha256(
                        _signature_bytes(signature)
                    ).hexdigest(),
                },
            )
    if failure:
        raise WalletOwnershipError(failure)
    return challenge.asset


def proven_assets():
    """Recheck proof and authorized recipient every time, never trust screenshots."""
    result = {}
    for asset, address in MERCHANT_ADDRESSES.items():
        proof = MerchantWalletProof.objects.select_related("challenge", "owner").filter(
            asset=asset, address__iexact=address,
        ).first()
        result[asset] = bool(
            proof and proof.owner.is_active and proof.owner.is_superuser
            and proof.challenge.owner_id == proof.owner_id
            and proof.challenge.asset == asset
            and proof.challenge.address.lower() == address.lower()
            and proof.challenge.verified_at == proof.verified_at
            and proof.challenge.used_at is not None
            and proof.signature_scheme == SIGNATURE_SCHEMES[asset]
        )
    return result
