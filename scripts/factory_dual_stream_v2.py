"""F01V2: authenticated, bounded-memory encrypted streaming to TWO independent stores.

NO account credentials, network sessions, paid storage, SQL connection,
production deployment or filesystem side effects are embedded here.
A caller supplies independent upload/read-back functions for two distinct
owner accounts. Remote read-back checks each ciphertext part before it is
accepted; the authenticated completion manifest is uploaded LAST. If a
transfer fails, incomplete encrypted parts might remain; this does not authorize
any deletion. This algorithm does NOT prove a consistent live SQL snapshot,
media completeness, provider quota, owner-held RSA private key recoverability,
backup freshness, or a successful offline restore. Never call it with a live
factory stream without those independent approvals and prerequisites.
"""
from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
from typing import BinaryIO, Callable

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAGIC = b'F01V2\x00\x02'
SCHEMA = 'factory.dual-encrypted-stream.f01v2'
MIN_CHUNK = 4096
MAX_CHUNK = 8 * 1024 * 1024
MAX_SOURCE = 1 << 40  # 1 TiB; caller should set a smaller admission limit
MAX_MANIFEST = 2 * 1024 * 1024
MAX_PARTS = 131072
AAD_META_LEN = len(MAGIC) + 16 + 4 + 1 + 4


@dataclass(frozen=True)
class DualStoreReceipt:
    manifest_sha256: str
    plaintext_bytes: int
    ciphertext_bytes: int
    parts: int
    claimed_owner_a: str
    claimed_owner_b: str
    cipher_parts_mirrored_and_readback_verified: bool = True
    cloud_account_identity_verified_by_this_code: bool = False
    current_source_consistency_verified: bool = False
    restores_verified: bool = False
    commercial_release_authorized: bool = False


def _canonical(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=True,
                      separators=(',', ':'), allow_nan=False).encode('ascii')


def _sha(x: bytes) -> str:
    return hashlib.sha256(x).hexdigest()


def _manifest_key(key: bytes, run_id: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32,
                salt=run_id, info=b'MOJ-F01V2-PRIVATE-MANIFEST').derive(key)


def _read_chunk(source: BinaryIO, limit: int) -> bytes:
    blocks = []
    total = 0
    while total < limit:
        piece = source.read(limit - total)
        if type(piece) is not bytes:
            raise ValueError('NON_BINARY_SOURCE')
        if not piece:
            break
        total += len(piece)
        blocks.append(piece)
    return b''.join(blocks)


def _b64decode(s: str) -> bytes:
    if type(s) is not str or len(s) > 8192:
        raise ValueError('INVALID_BASE64_LENGTH')
    return base64.b64decode(s, validate=True)


def _public_fingerprint(pem: bytes) -> tuple[object, str]:
    if type(pem) is not bytes or len(pem) > 16384:
        raise ValueError('INVALID_PUBLIC_PEM')
    pub = serialization.load_pem_public_key(pem)
    if not isinstance(pub, rsa.RSAPublicKey) or pub.key_size < 3072:
        raise ValueError('PUBLIC_RSA_TOO_WEAK_OR_WRONG_TYPE')
    der = pub.public_bytes(serialization.Encoding.DER,
                           serialization.PublicFormat.SubjectPublicKeyInfo)
    return pub, _sha(der)


def _assert_two_stores(owner_a: str, owner_b: str, upload_a: Callable,
                       upload_b: Callable, read_a: Callable, read_b: Callable) -> None:
    if (type(owner_a) is not str or type(owner_b) is not str
            or not owner_a.strip() or not owner_b.strip()
            or owner_a.strip().casefold() == owner_b.strip().casefold()):
        raise ValueError('REQUIRES_TWO_INDEPENDENT_OWNER_ACCOUNTS')
    if not all(callable(x) for x in (upload_a, upload_b, read_a, read_b)):
        raise ValueError('MISSING_INDEPENDENT_UPLOAD_OR_READBACK')
    if upload_a == upload_b or read_a == read_b:
        raise ValueError('SAME_PROVIDER_CALLBACK_NOT_INDEPENDENT')


def _upload_and_read_back(name: str, payload: bytes, upload: Callable,
                          read: Callable) -> None:
    # The adapters must authenticate owner identity and privately own each
    # independent storage object; this function verifies returned bytes only.
    upload(name, payload)
    observed = read(name)
    if type(observed) is not bytes or len(observed) != len(payload) or not hmac.compare_digest(
            hashlib.sha256(observed).digest(), hashlib.sha256(payload).digest()):
        raise ValueError('REMOTE_CIPHERTEXT_READBACK_MISMATCH')


def encrypt_stream_to_dual_stores(
    source: BinaryIO, *, public_pem: bytes, trusted_public_spki_sha256: str,
    owner_a: str, owner_b: str,
    upload_a: Callable[[str, bytes], object], upload_b: Callable[[str, bytes], object],
    read_a: Callable[[str], bytes], read_b: Callable[[str], bytes],
    chunk_bytes: int = 4 * 1024 * 1024, max_source_bytes: int = MAX_SOURCE,
) -> DualStoreReceipt:
    """Bounded-memory crypto and authenticated two-provider byte read-back.

    NEVER supply buyer data, secrets, filenames or tokens in callback names.
    No provider login, quota, consent, storage billing or network action here.
    Caller must externally enforce provider quota and full source consistency.
    """
    _assert_two_stores(owner_a, owner_b, upload_a, upload_b, read_a, read_b)
    if (type(chunk_bytes) is not int or not MIN_CHUNK <= chunk_bytes <= MAX_CHUNK
            or type(max_source_bytes) is not int or
            not 1 <= max_source_bytes <= MAX_SOURCE):
        raise ValueError('INVALID_STREAM_BOUNDS')
    pub, pub_fp = _public_fingerprint(public_pem)
    if (type(trusted_public_spki_sha256) is not str or
            not hmac.compare_digest(pub_fp, trusted_public_spki_sha256)):
        raise ValueError('PUBLIC_KEY_NOT_IN_OWNER_ALLOWLIST')
    secret_key = secrets.token_bytes(32)
    run_id = secrets.token_bytes(16)
    nonce_prefix = secrets.token_bytes(8)
    wrapped = pub.encrypt(secret_key, padding.OAEP(
        mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    cipher = AESGCM(secret_key)
    first = _read_chunk(source, chunk_bytes)
    if not first:
        raise ValueError('EMPTY_BACKUP_STREAM')
    idx = 0
    plain_total = 0
    cipher_total = 0
    parts = []
    current = first
    while current:
        following = _read_chunk(source, chunk_bytes)
        final = not following
        idx += 1
        if idx > MAX_PARTS or idx >= 2 ** 32:
            raise ValueError('TOO_MANY_BACKUP_PARTS')
        plain_total += len(current)
        if plain_total > max_source_bytes:
            raise ValueError('BACKUP_STREAM_EXCEEDS_ADMITTED_SOURCE_BYTES')
        seq = idx.to_bytes(4, 'big')
        nonce = nonce_prefix + seq
        header = (MAGIC + run_id + seq + (b'\x01' if final else b'\x00')
                  + len(current).to_bytes(4, 'big'))
        payload = header + cipher.encrypt(nonce, current, header)
        name = f'f01v2-{run_id.hex()}-{idx:06d}.enc'
        _upload_and_read_back(name, payload, upload_a, read_a)
        _upload_and_read_back(name, payload, upload_b, read_b)
        cipher_total += len(payload)
        parts.append({'name': name, 'index': idx, 'cipher_bytes': len(payload),
                      'cipher_sha256': _sha(payload), 'plain_bytes': len(current)})
        current = following
    manifest = {
        'schema': SCHEMA, 'run_id': run_id.hex(),
        'public_key_spki_sha256': pub_fp,
        'wrapped_key': base64.b64encode(wrapped).decode('ascii'),
        'nonce_prefix': base64.b64encode(nonce_prefix).decode('ascii'),
        'chunk_limit': chunk_bytes,
        'plain_total': plain_total,
        'cipher_total': cipher_total,
        'parts': parts,
        'owner_refs': sorted([hmac.new(secret_key, b'F01V2:OWNER:'+x.encode('utf-8'), hashlib.sha256).hexdigest()[:32] for x in (owner_a, owner_b)]),
        'source_consistency_external': False,
        'restore_verified': False,
    }
    manifest_mac = hmac.new(_manifest_key(secret_key, run_id),
                            _canonical(manifest), hashlib.sha256).hexdigest()
    manifest['manifest_mac_sha256'] = manifest_mac
    manifest_bytes = _canonical(manifest)
    if len(manifest_bytes) > MAX_MANIFEST:
        raise ValueError('MANIFEST_TOO_LARGE')
    manifest_name = f'f01v2-{run_id.hex()}-manifest.json'
    _upload_and_read_back(manifest_name, manifest_bytes, upload_a, read_a)
    _upload_and_read_back(manifest_name, manifest_bytes, upload_b, read_b)
    return DualStoreReceipt(_sha(manifest_bytes), plain_total, cipher_total,
                            idx, owner_a, owner_b)


def decrypt_to_isolated_file(
    manifest_bytes: bytes, *, read_chunk: Callable[[str], bytes],
    private_pem: bytes, private_password: bytes | None,
    expected_public_spki_sha256: str, output_path: str | Path,
) -> int:
    """Offline-only restore into NEW file; nothing touches live services.

    Only finalizes the output after verifying manifest MAC and EVERY AES-GCM
    chunk tag, part length/order and SHA-256. On failure, removes only the
    newly generated .tmp output, not an existing source or a remote backup.
    """
    if type(manifest_bytes) is not bytes or not 1 <= len(manifest_bytes) <= MAX_MANIFEST:
        raise ValueError('INVALID_MANIFEST_BYTES')
    manifest = json.loads(manifest_bytes)
    if type(manifest) is not dict or manifest.get('schema') != SCHEMA:
        raise ValueError('UNKNOWN_BACKUP_SCHEMA')
    if set(manifest) != {
        'schema','run_id','public_key_spki_sha256','wrapped_key','nonce_prefix',
        'chunk_limit','plain_total','cipher_total','parts','owner_refs',
        'source_consistency_external','restore_verified','manifest_mac_sha256'
    }:
        raise ValueError('UNEXPECTED_MANIFEST_FIELDS')
    if type(manifest.get('manifest_mac_sha256')) is not str:
        raise ValueError('MISSING_MANIFEST_MAC')
    mac = manifest.pop('manifest_mac_sha256')
    run_id = bytes.fromhex(manifest['run_id'])
    if len(run_id) != 16:
        raise ValueError('INVALID_BACKUP_RUN')
    if (type(expected_public_spki_sha256) is not str or
            manifest['public_key_spki_sha256'] != expected_public_spki_sha256):
        raise ValueError('WRONG_BACKUP_RECIPIENT')
    key = serialization.load_pem_private_key(private_pem,password=private_password)
    if key.key_size < 3072:
        raise ValueError('PRIVATE_RSA_TOO_WEAK')
    public_der = key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    if _sha(public_der) != expected_public_spki_sha256:
        raise ValueError('PRIVATE_PUBLIC_RECIPIENT_MISMATCH')
    secret_key = key.decrypt(_b64decode(manifest['wrapped_key']), padding.OAEP(
        mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    if len(secret_key) != 32:
        raise ValueError('INVALID_AES_SESSION_KEY')
    expected_mac = hmac.new(_manifest_key(secret_key,run_id),
                            _canonical(manifest),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_mac,mac):
        raise ValueError('MANIFEST_AUTHENTICATION_FAILED')
    chunks = manifest['parts']
    if (type(chunks) is not list or not chunks or len(chunks) > MAX_PARTS or
            type(manifest.get('chunk_limit')) is not int or not MIN_CHUNK <= manifest['chunk_limit'] <= MAX_CHUNK):
        raise ValueError('INVALID_MANIFEST_PARTS')
    nonce_prefix = _b64decode(manifest['nonce_prefix'])
    if len(nonce_prefix) != 8:
        raise ValueError('INVALID_NONCE_PREFIX')
    dst = Path(output_path)
    if dst.exists() or dst.is_symlink():
        raise FileExistsError('OUTPUT_EXISTS')
    tmp = dst.with_name(dst.name+'.f01v2-temp-'+run_id.hex())
    flag = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os,'O_NOFOLLOW',0)
    written = 0
    observed_total = 0
    seen_names = set()
    aes = AESGCM(secret_key)
    with os.fdopen(os.open(tmp,flag,0o600),'wb') as out:
        try:
            for expected_index,entry in enumerate(chunks,1):
                if type(entry) is not dict or set(entry) != {
                        'name','index','cipher_bytes','cipher_sha256','plain_bytes'}:
                    raise ValueError('INVALID_PART_ENTRY')
                name = f'f01v2-{run_id.hex()}-{expected_index:06d}.enc'
                if name in seen_names or entry['name'] != name or entry['index'] != expected_index:
                    raise ValueError('PART_ORDER_MISMATCH')
                seen_names.add(name)
                blob = read_chunk(name)
                if type(blob) is not bytes or len(blob) != entry['cipher_bytes'] or _sha(blob) != entry['cipher_sha256']:
                    raise ValueError('REMOTE_PART_HASH_MISMATCH')
                header = blob[:AAD_META_LEN]
                m = len(MAGIC)
                if (header[:m] != MAGIC or header[m:m+16] != run_id or
                        header[m+16:m+20] != expected_index.to_bytes(4,'big') or
                        header[m+20:m+21] != (b'\x01' if expected_index == len(chunks) else b'\x00')):
                    raise ValueError('PART_HEADER_MISMATCH')
                size = int.from_bytes(header[m+21:m+25],'big')
                if size != entry['plain_bytes'] or not 1 <= size <= manifest['chunk_limit']:
                    raise ValueError('PART_PLAINTEXT_SIZE_MISMATCH')
                plain = aes.decrypt(nonce_prefix + expected_index.to_bytes(4,'big'), blob[AAD_META_LEN:], header)
                if len(plain) != size:
                    raise ValueError('PART_DECRYPTED_SIZE_MISMATCH')
                out.write(plain)
                written += len(plain)
                observed_total += len(blob)
            if written != manifest['plain_total'] or observed_total != manifest['cipher_total']:
                raise ValueError('BACKUP_TOTAL_MISMATCH')
            out.flush()
            os.fsync(out.fileno())
        except BaseException:
            try:
                out.close()
            finally:
                tmp.unlink(missing_ok=True)
            raise
    try:
        # os.link rather than os.replace prevents overwrite of an existing
        # destination, including races after the initial exists() check.
        os.link(tmp,dst,follow_symlinks=False)
        tmp.unlink()
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return written
