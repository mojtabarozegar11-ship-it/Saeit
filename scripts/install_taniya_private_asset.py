#!/usr/bin/env python3
"""Install the Taniya PDF from an encrypted, checksum-pinned transfer bundle.

The PDF and its wrapped AES/HMAC keys are encrypted before entering GitHub.
Only the cPanel host holds the short-lived RSA private key.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile

HOME = Path("/home/zomorod2")
INCOMING = HOME / "MojPlayWin_Private_Uploads" / "taniya-transfer.tar.gz"
KEY_DIR = HOME / ".mpw-taniya-transfer"
PRIVATE_KEY = KEY_DIR / "private.pem"
ASSET_ROOT = HOME / "MojPlayWin_Private_Assets"
TARGET_DIR = ASSET_ROOT / "taniya-little-baker-worms"
TARGET = TARGET_DIR / "Taniya_and_the_Little_Baker_Worms.pdf"
EXPECTED_PRODUCT = "mojplaywin-taniya-little-baker-worms"
EXPECTED_SHA = "2f6dace4e5bc09ffe5f8d7a677ddff4980fe00de94b7c2ea5b286d1303901d48"
EXPECTED_SIZE = 13876137
PRIVATE_RELATIVE = "taniya-little-baker-worms/Taniya_and_the_Little_Baker_Worms.pdf"
MAX_CIPHER_SIZE = 20_000_000


def require_private_dir(path):
    if path.is_symlink():
        raise RuntimeError("Refusing symlink in private asset path")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
    if not path.is_dir() or path.stat().st_mode & 0o077:
        raise RuntimeError("Private directory permissions are too broad")


def read_members():
    if INCOMING.is_symlink() or not INCOMING.is_file():
        raise RuntimeError("Encrypted Taniya transfer archive is missing")
    if INCOMING.stat().st_size > MAX_CIPHER_SIZE:
        raise RuntimeError("Encrypted transfer archive exceeds its limit")
    expected = {"book.enc", "key.wrap", "manifest.json"}
    with tarfile.open(INCOMING, "r:gz") as archive:
        members = archive.getmembers()
        if {m.name for m in members} != expected or len(members) != 3:
            raise RuntimeError("Unexpected encrypted archive contents")
        if any(not m.isfile() or m.issym() or m.islnk() or "/" in m.name or "\\\\" in m.name for m in members):
            raise RuntimeError("Unsafe archive member")
        limits = {"book.enc": MAX_CIPHER_SIZE, "key.wrap": 1024, "manifest.json": 4096}
        output = {}
        for member in members:
            if member.size > limits[member.name]:
                raise RuntimeError("Encrypted archive member is oversized")
            stream = archive.extractfile(member)
            if stream is None:
                raise RuntimeError("Archive member cannot be read")
            output[member.name] = stream.read(limits[member.name] + 1)
            if len(output[member.name]) != member.size:
                raise RuntimeError("Truncated archive member")
        return output


def install():
    if os.getuid() != PRIVATE_KEY.stat().st_uid:
        raise RuntimeError("Transfer key owner mismatch")
    if PRIVATE_KEY.is_symlink() or PRIVATE_KEY.stat().st_mode & 0o077:
        raise RuntimeError("Transfer key is not private")
    members = read_members()
    doc = json.loads(members["manifest.json"].decode("utf-8"))
    if (doc.get("product_id") != EXPECTED_PRODUCT
        or doc.get("filename") != TARGET.name
        or doc.get("sha256") != EXPECTED_SHA
        or doc.get("size_bytes") != EXPECTED_SIZE
        or doc.get("cipher") != "AES-256-CBC"
        or doc.get("kdf") != "PBKDF2-HMAC-SHA256"
        or doc.get("iterations") != 250000):
        raise RuntimeError("Taniya asset manifest mismatch")
    cipher = members["book.enc"]
    if len(cipher) > MAX_CIPHER_SIZE:
        raise RuntimeError("Encrypted PDF exceeds its limit")
    if hashlib.sha256(cipher).hexdigest() != doc.get("cipher_sha256"):
        raise RuntimeError("Encrypted PDF checksum mismatch")
    require_private_dir(ASSET_ROOT)
    require_private_dir(TARGET_DIR)
    temp_dir = Path(tempfile.mkdtemp(prefix=".taniya-install-", dir=str(TARGET_DIR)))
    temp_dir.chmod(0o700)
    try:
        cipher_path = temp_dir / "book.enc"
        wrapped_path = temp_dir / "key.wrap"
        manifest_path = temp_dir / "manifest.json"
        keys_path = temp_dir / "keys.txt"
        pdf_path = temp_dir / "book.pdf"
        for path, value in ((cipher_path, cipher), (wrapped_path, members["key.wrap"]), (manifest_path, members["manifest.json"])):
            with path.open("xb") as out:
                out.write(value)
            path.chmod(0o600)
        subprocess.run([
            "openssl", "pkeyutl", "-decrypt", "-inkey", str(PRIVATE_KEY),
            "-in", str(wrapped_path), "-out", str(keys_path),
            "-pkeyopt", "rsa_padding_mode:oaep", "-pkeyopt", "rsa_oaep_md:sha256",
        ], check=True, timeout=20, capture_output=True)
        keys_path.chmod(0o600)
        secret_lines = keys_path.read_text("ascii").splitlines()
        if len(secret_lines) != 2 or re.fullmatch(r"[0-9a-f]{64}", secret_lines[0]) is None or re.fullmatch(r"[0-9a-f]{64}", secret_lines[1]) is None:
            raise RuntimeError("Invalid wrapped transfer keys")
        password, mac_key = secret_lines
        actual_mac = hmac.new(bytes.fromhex(mac_key), cipher, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(actual_mac, doc.get("cipher_hmac_sha256", "")):
            raise RuntimeError("Encrypted PDF authentication failed")
        subprocess.run([
            "openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", "250000",
            "-pass", "file:" + str(keys_path), "-in", str(cipher_path), "-out", str(pdf_path),
        ], check=True, timeout=90, capture_output=True)
        pdf_path.chmod(0o600)
        digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        if pdf_path.stat().st_size != EXPECTED_SIZE or digest != EXPECTED_SHA:
            raise RuntimeError("Decrypted Taniya PDF checksum or length mismatch")
        if not pdf_path.read_bytes()[:5] == b"%PDF-":
            raise RuntimeError("Decrypted asset is not a PDF")
        if TARGET.exists() or TARGET.is_symlink():
            if TARGET.is_symlink() or not TARGET.is_file() or hashlib.sha256(TARGET.read_bytes()).hexdigest() != EXPECTED_SHA:
                raise RuntimeError("Existing Taniya asset differs; refusing overwrite")
            pdf_path.unlink()
            print("TANIYA_PRIVATE_PDF_ALREADY_PRESENT")
        else:
            os.link(pdf_path, TARGET, follow_symlinks=False)
            TARGET.chmod(0o600)
            pdf_path.unlink()
            print("TANIYA_PRIVATE_PDF_INSTALLED")
    finally:
        shutil.rmtree(temp_dir)

    import sys
    sys.path.insert(0, "/home/zomorod2/Saeit-staging")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from decimal import Decimal
    from django.db import transaction
    from core.models import Product
    with transaction.atomic():
        product = Product.objects.filter(title__iexact="Taniya and the Little Baker Worms").first()
        if product is None or product.active is not False or product.currency != "USD" or product.price != Decimal("4.00"):
            raise RuntimeError("Taniya draft product is missing or unexpectedly active")
        meta = product.metadata if isinstance(product.metadata, dict) else {}
        if meta.get("product_id") != EXPECTED_PRODUCT:
            raise RuntimeError("Taniya product identity mismatch")
        meta["pdf_sha256"] = EXPECTED_SHA
        meta["fulfillment_status"] = "private_asset_installed_checkout_disabled"
        meta["private_asset_installed"] = True
        meta["mpw_commerce"] = {
            "enabled": False,
            "fulfillment": "digital",
            "private_file": PRIVATE_RELATIVE,
            "sha256": EXPECTED_SHA,
            "filename": TARGET.name,
        }
        product.metadata = meta
        product.full_clean()
        product.save(update_fields=["metadata"])
    if TARGET.is_symlink() or not TARGET.is_file() or TARGET.stat().st_mode & 0o077:
        raise RuntimeError("Installed Taniya asset permissions are unsafe")
    if hashlib.sha256(TARGET.read_bytes()).hexdigest() != EXPECTED_SHA:
        raise RuntimeError("Installed Taniya asset failed final checksum")
    INCOMING.unlink()
    if PRIVATE_KEY.is_file() and not PRIVATE_KEY.is_symlink():
        PRIVATE_KEY.unlink()
    public_key = KEY_DIR / "public.pem"
    if public_key.is_file() and not public_key.is_symlink():
        public_key.unlink()
    if KEY_DIR.is_dir() and not KEY_DIR.is_symlink():
        KEY_DIR.rmdir()
    print("TANIYA_PRIVATE_ASSET_VERIFIED")
    print("TANIYA_DB_PRIVATE_FILE_CONFIGURED_CHECKOUT_DISABLED")
    print("TANIYA_CUSTOMER_PAYMENTS_NOT_YET_ENABLED")


if __name__ == "__main__":
    install()
