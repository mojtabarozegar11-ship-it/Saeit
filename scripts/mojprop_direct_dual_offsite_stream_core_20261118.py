"""Bounded-memory AES-256-GCM / RSA-OAEP source-to-TWO-private-stores core.

IMPORTANT: This module is NOT an uploader, CLI, live backup, SQL snapshotter,
production deployment, restore authorization or a substitute for independent
source consistency. The caller must independently authenticate TWO genuinely
separate owner cloud accounts, fetch actual free quotas, validate private ACLs,
capture consistent current MySQL+all app/media via pinned SSH and verify complete
restore. ChatGPT connector OAuth is NOT passed to the VPS.

No local plaintext/ciphertext backup file is written. Each <= 8MiB chunk is
AES-256-GCM encrypted, put once into each independent private sink, read back
byte-for-byte from BOTH, and chained into a terminal manifest only after
exact expected source length, EOF and all part readbacks. Failure leaves
private incomplete parts untouched: no cleanup, delete or implicit retry.
An offline isolated restore must compare both clouds and verify GCM + full
plaintext digest; never target a live DB or production directory.

RSA public key on source, RSA private key held OFF both VPS and cloud.
The module cannot cryptographically attest the upstream producer's own
source legitimacy; separately signed source provenance + isolated SQL/media
replay remain mandatory business gates.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import os
import re
from typing import BinaryIO, Protocol

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SCHEMA = "mojprop-private-dual-offsite-aead.v1"
STEM = re.compile(r"mojplaywin_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{16}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
PART_DEFAULT = 4 * 1024**2
PART_MIN = 64 * 1024
PART_MAX = 8 * 1024**2
MAX_SOURCE = 48 * 1024**3
MIN_RESERVE = 512 * 1024**2
MAX_MANIFEST = 256 * 1024
MAX_PARTS = (MAX_SOURCE + PART_MIN - 1) // PART_MIN


class DualOffsiteDenied(ValueError):
    """Incomplete, altered, impersonated or unreviewed backup is rejected."""


class PrivateSink(Protocol):
    def put_once(self, key: str, value: bytes) -> None: ...
    def read_exact(self, key: str, max_bytes: int) -> bytes: ...


@dataclass(frozen=True)
class ProviderReview:
    # This is an EXTERNAL claim, not authenticated by this module.
    account_id: str
    oauth_owner_account_verified: bool
    owner_private_acl_verified: bool
    capacity_from_provider_api_verified: bool
    readback_supported_verified: bool
    free_bytes: int


def encoded(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _public_key(pem: bytes):
    try:
        key = serialization.load_pem_public_key(pem)
    except (ValueError, TypeError) as exc:
        raise DualOffsiteDenied("INVALID_RECOVERY_PUBLIC_KEY") from exc
    if not isinstance(key, rsa.RSAPublicKey) or key.key_size < 3072:
        raise DualOffsiteDenied("RECOVERY_RSA_PUBLIC_KEY_BELOW_3072")
    return key


def _source_name(set_id: str, kind: str) -> str:
    if type(set_id) is not str or STEM.fullmatch(set_id) is None:
        raise DualOffsiteDenied("INVALID_SET_ID")
    if kind not in ("mysql", "files"):
        raise DualOffsiteDenied("INVALID_KIND")
    return "mojprop-recovery/" + set_id + "/" + kind + "/"


def _source_size(source_bytes: int, part_size: int) -> None:
    if type(source_bytes) is not int or not (1 <= source_bytes <= MAX_SOURCE):
        raise DualOffsiteDenied("INVALID_EXPECTED_SOURCE_SIZE")
    if type(part_size) is not int or not PART_MIN <= part_size <= PART_MAX:
        raise DualOffsiteDenied("INVALID_PART_SIZE")


def _destinations(sinks: tuple[PrivateSink, PrivateSink],
                  reviews: tuple[ProviderReview, ProviderReview],
                  source_bytes: int, part_size: int) -> None:
    if type(sinks) is not tuple or len(sinks) != 2 or sinks[0] is sinks[1]:
        raise DualOffsiteDenied("REQUIRE_TWO_INDEPENDENT_SINK_OBJECTS")
    if type(reviews) is not tuple or len(reviews) != 2:
        raise DualOffsiteDenied("REQUIRE_TWO_PROVIDER_REVIEWS")
    names = []
    parts = (source_bytes + part_size - 1) // part_size
    # Loose but safe quota bound for noncompressed AEAD+manifest per provider.
    required = source_bytes + 28 * parts + MAX_MANIFEST + MIN_RESERVE
    for rev in reviews:
        if type(rev) is not ProviderReview:
            raise DualOffsiteDenied("UNVERIFIED_PROVIDER_EVIDENCE")
        if not isinstance(rev.account_id, str) or not re.fullmatch(
                r"[A-Za-z0-9_.-]{3,96}", rev.account_id):
            raise DualOffsiteDenied("INVALID_OWNER_ACCOUNT_ID")
        if not all(type(v) is bool and v for v in (
                rev.oauth_owner_account_verified,rev.owner_private_acl_verified,
                rev.capacity_from_provider_api_verified,
                rev.readback_supported_verified)):
            raise DualOffsiteDenied("DESTINATION_NOT_OWNER_VERIFIED")
        if type(rev.free_bytes) is not int or rev.free_bytes < required:
            raise DualOffsiteDenied("PROVIDER_FREE_QUOTA_BELOW_PRIVATE_BACKUP_SIZE")
        names.append(rev.account_id)
    if names[0] == names[1]:
        raise DualOffsiteDenied("SAME_ACCOUNT_CANNOT_COUNT_AS_TWO_COPIES")


def _put_and_read_both(sinks, key: str, value: bytes) -> None:
    for sink in sinks:
        sink.put_once(key, value)
    for sink in sinks:
        echoed = sink.read_exact(key, len(value) + 1)
        if type(echoed) is not bytes or echoed != value:
            raise DualOffsiteDenied("PRIVATE_PROVIDER_READBACK_MISMATCH")


def _part_aad(set_id: str, kind: str, index: int,
              expected: int, previous: str) -> bytes:
    return encoded({"schema":SCHEMA,"set_id":set_id,"kind":kind,
                    "index":index,"source_bytes":expected,
                    "previous_cipher_sha256":previous})


def stream_to_two_private_sinks(source: BinaryIO, sinks: tuple[PrivateSink, PrivateSink],
                                reviews: tuple[ProviderReview, ProviderReview],
                                public_pem: bytes, *, set_id: str, kind: str,
                                expected_source_bytes: int,
                                part_size: int=PART_DEFAULT) -> dict:
    """Private-only transport. NO production/restore/financial approval."""
    prefix = _source_name(set_id,kind)
    _source_size(expected_source_bytes,part_size)
    _destinations(sinks,reviews,expected_source_bytes,part_size)
    public = _public_key(public_pem)
    master = os.urandom(32)
    wrapped = public.encrypt(master,padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),label=None))
    public_der = public.public_bytes(serialization.Encoding.DER,
                                      serialization.PublicFormat.SubjectPublicKeyInfo)
    aead=AESGCM(master)
    plain_hash=hashlib.sha256()
    cipher_chain=hashlib.sha256()
    previous="0"*64
    read_total=0
    count=0
    while read_total < expected_source_bytes:
        want=min(part_size,expected_source_bytes-read_total)
        block=source.read(want)
        # Buffered SSH can return less than requested; the caller must use a
        # wrapper that reads *exactly* want or EOF. Do not accept short reads
        # as end-of-file without repeated read; special streams may be short.
        if type(block) is not bytes or not block:
            raise DualOffsiteDenied("SOURCE_ENDED_BEFORE_EXPECTED_LENGTH")
        while len(block) < want:
            more=source.read(want-len(block))
            if type(more) is not bytes or not more:
                raise DualOffsiteDenied("SOURCE_ENDED_BEFORE_EXPECTED_LENGTH")
            block+=more
        aad=_part_aad(set_id,kind,count,expected_source_bytes,previous)
        nonce=os.urandom(12)
        encrypted=nonce+aead.encrypt(nonce,block,aad)
        part_hash=digest(encrypted)
        key=prefix+f"{count:08d}.gcm"
        _put_and_read_both(sinks,key,encrypted)
        cipher_chain.update(bytes.fromhex(part_hash))
        plain_hash.update(block)
        previous=part_hash
        read_total+=len(block)
        count+=1
        if count>MAX_PARTS:
            raise DualOffsiteDenied("TOO_MANY_ENCRYPTED_PARTS")
    if source.read(1)!=b"":
        raise DualOffsiteDenied("SOURCE_HAS_UNEXPECTED_EXTRA_BYTES")
    manifest={
        "schema":SCHEMA,"set_id":set_id,"kind":kind,
        "source_bytes":read_total,"part_size":part_size,
        "part_count":count,"plaintext_sha256":plain_hash.hexdigest(),
        "cipher_hash_chain_sha256":cipher_chain.hexdigest(),
        "last_part_sha256":previous,
        "wrapped_aes256_key_b64":base64.b64encode(wrapped).decode("ascii"),
        "recipient_public_key_sha256":digest(public_der),
        "algorithm":"RSA-OAEP-SHA256+AES-256-GCM",
        "requires_second_kind_and_isolated_restore":True,
    }
    blob=encoded(manifest)
    if len(blob)>MAX_MANIFEST:
        raise DualOffsiteDenied("MANIFEST_TOO_LARGE")
    _put_and_read_both(sinks,prefix+"manifest.json",blob)
    return {
        "classification":"PRIVATE_KIND_AEAD_CHUNKS_READBACK_COMPLETE_NOT_RESTORED",
        "set_id":set_id,"kind":kind,"parts":count,
        "plaintext_bytes":read_total,
        "recipient_pubkey_sha256":manifest["recipient_public_key_sha256"],
        "two_provider_part_readbacks_completed":True,
        "terminal_kind_manifests_read_back":True,
        "full_mysql_plus_media_pair_proven":False,
        "independently_restored":False,
        "production_deployed":False,"payment_collected":False,
        "server_oauth_authenticated_by_this_library":False,
        "source_consistency_authenticated_by_this_library":False,
    }


def isolated_restore_from_two_private_sinks(sinks: tuple[PrivateSink, PrivateSink],
                                             private_pem: bytes, password: bytes | None,
                                             *, set_id: str, kind: str,
                                             isolated_output: BinaryIO,
                                             expected_pubkey_sha256: str) -> dict:
    """Only an independent quarantined output, NEVER live database, as caller."""
    prefix=_source_name(set_id,kind)
    if type(sinks) is not tuple or len(sinks)!=2 or sinks[0] is sinks[1]:
        raise DualOffsiteDenied("RESTORE_REQUIRES_TWO_INDEPENDENT_INPUT_SINKS")
    if type(expected_pubkey_sha256) is not str or not HEX64.fullmatch(expected_pubkey_sha256):
        raise DualOffsiteDenied("MISSING_PINNED_RECOVERY_PUBLIC_KEY")
    raw=[sink.read_exact(prefix+"manifest.json",MAX_MANIFEST+1) for sink in sinks]
    if any(type(v) is not bytes or not v or len(v)>MAX_MANIFEST for v in raw):
        raise DualOffsiteDenied("INVALID_MANIFEST_LENGTH")
    if raw[0]!=raw[1]:
        raise DualOffsiteDenied("PRIVATE_CLOUD_MANIFESTS_DISAGREE")
    try:
        obj=json.loads(raw[0])
    except (ValueError,UnicodeError) as exc:
        raise DualOffsiteDenied("INVALID_PRIVATE_MANIFEST_JSON") from exc
    if (type(obj) is not dict or obj.get("schema")!=SCHEMA or
            obj.get("set_id")!=set_id or obj.get("kind")!=kind or
            obj.get("recipient_public_key_sha256")!=expected_pubkey_sha256 or
            obj.get("algorithm")!="RSA-OAEP-SHA256+AES-256-GCM" or
            obj.get("requires_second_kind_and_isolated_restore") is not True):
        raise DualOffsiteDenied("MANIFEST_SOURCE_OR_RECIPIENT_NOT_PINNED")
    size=obj.get("source_bytes")
    part_size=obj.get("part_size")
    _source_size(size,part_size)
    expected_parts=(size+part_size-1)//part_size
    if (type(obj.get("part_count")) is not int or
            obj["part_count"]!=expected_parts or
            not isinstance(obj.get("plaintext_sha256"),str) or
            not HEX64.fullmatch(obj["plaintext_sha256"]) or
            not isinstance(obj.get("cipher_hash_chain_sha256"),str) or
            not HEX64.fullmatch(obj["cipher_hash_chain_sha256"]) or
            not isinstance(obj.get("last_part_sha256"),str) or
            not HEX64.fullmatch(obj["last_part_sha256"])):
        raise DualOffsiteDenied("MALFORMED_TERMINAL_MANIFEST")
    try:
        private=serialization.load_pem_private_key(private_pem,password=password)
    except (ValueError,TypeError) as exc:
        raise DualOffsiteDenied("INVALID_OFFLINE_RECOVERY_PRIVATE_KEY") from exc
    if not isinstance(private,rsa.RSAPrivateKey) or private.key_size<3072:
        raise DualOffsiteDenied("RECOVERY_PRIVATE_RSA_TOO_WEAK")
    pub=private.public_key().public_bytes(serialization.Encoding.DER,
                                           serialization.PublicFormat.SubjectPublicKeyInfo)
    if digest(pub)!=expected_pubkey_sha256:
        raise DualOffsiteDenied("RECOVERY_KEY_PAIR_MISMATCH")
    try:
        wrapped=base64.b64decode(obj["wrapped_aes256_key_b64"],validate=True)
        key=private.decrypt(wrapped,padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),label=None))
    except (ValueError,TypeError,KeyError) as exc:
        raise DualOffsiteDenied("INVALID_RSA_OAEP_WRAPPED_KEY") from exc
    if len(key)!=32:
        raise DualOffsiteDenied("INVALID_UNWRAPPED_AES_KEY")
    aead=AESGCM(key)
    sha=hashlib.sha256()
    chain=hashlib.sha256()
    previous="0"*64
    wrote=0
    for i in range(expected_parts):
        part_key=prefix+f"{i:08d}.gcm"
        length=min(part_size,size-wrote)+12+16
        values=[sink.read_exact(part_key,length+1) for sink in sinks]
        if any(type(v) is not bytes or len(v)!=length for v in values):
            raise DualOffsiteDenied("ENCRYPTED_PART_MISSING_OR_BAD_SIZE")
        if values[0]!=values[1]:
            raise DualOffsiteDenied("TWO_CLOUDS_PART_MISMATCH")
        fingerprint=digest(values[0])
        aad=_part_aad(set_id,kind,i,size,previous)
        try:
            clear=aead.decrypt(values[0][:12],values[0][12:],aad)
        except Exception as exc:
            raise DualOffsiteDenied("AEAD_AUTHENTICATION_FAILED") from exc
        if len(clear)!=length-28:
            raise DualOffsiteDenied("DECRYPTED_PART_LENGTH_CHANGED")
        isolated_output.write(clear)
        sha.update(clear)
        chain.update(bytes.fromhex(fingerprint))
        previous=fingerprint
        wrote+=len(clear)
    if (wrote!=size or sha.hexdigest()!=obj["plaintext_sha256"] or
            chain.hexdigest()!=obj["cipher_hash_chain_sha256"] or
            previous!=obj["last_part_sha256"]):
        raise DualOffsiteDenied("TERMINAL_MANIFEST_INTEGRITY_MISMATCH")
    return {
        "classification":"INDEPENDENT_KIND_AEAD_REPLAY_VERIFIED",
        "set_id":set_id,"kind":kind,"decrypted_bytes":wrote,
        "two_private_copies_independently_read":True,
        "full_mysql_plus_media_pair_independently_restored":False,
        "isolated_sql_import_performed_by_this_library":False,
        "isolated_file_restore_performed_by_this_library":False,
        "production_writes":False,"customer_sales":0,
    }
