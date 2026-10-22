#!/usr/bin/env python3
"""Read-only MOJ1 Shasta monitor. Never loads a signing key or broadcasts."""
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import urllib.request

WALLET = "TWTBsKZPVuQgaGNbyJWJm9XR28g4wVBCNQ"
BASE = "https://api.shasta.trongrid.io"
ROOT = Path.home() / ".local/share/moj1-shasta-test-20261021"
MONITOR = ROOT / "monitor"


def assert_dir(path):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700:
        raise RuntimeError("PRIVATE_DIRECTORY_UNSAFE")


def assert_file(path, mode=0o600):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != mode:
        raise RuntimeError("PRIVATE_FILE_UNSAFE")


def validate_public_state():
    assert_dir(ROOT)
    public_path = ROOT / "wallet-public.json"
    assert_file(public_path)
    wallet = json.loads(public_path.read_text(encoding="utf-8"))
    if wallet.get("address_base58") != WALLET or wallet.get("network") != "Shasta-dedicated-test-use-only":
        raise RuntimeError("WALLET_PUBLIC_METADATA_MISMATCH")
    # Confirm presence and private permissions without opening any key.
    test_key = ROOT / "wallet.key"
    assert_file(test_key)
    if test_key.stat().st_size != 32:
        raise RuntimeError("TEST_KEY_SIZE_MISMATCH")

    signer_dir = ROOT / "governance-test-owners"
    assert_dir(signer_dir)
    owners_path = signer_dir / "owners-public.json"
    assert_file(owners_path)
    data = json.loads(owners_path.read_text(encoding="utf-8"))
    owners = data.get("owners")
    if data.get("network") != "SHASTA_TEST_ONLY" or data.get("production_approved") is not False:
        raise RuntimeError("GOVERNANCE_PUBLIC_METADATA_MISMATCH")
    if not isinstance(owners, list) or len(owners) != 3:
        raise RuntimeError("TEST_GOVERNANCE_OWNER_COUNT_MISMATCH")
    addresses = []
    for i, owner in enumerate(owners, 1):
        if owner.get("slot") != i or not isinstance(owner.get("address_base58"), str):
            raise RuntimeError("TEST_GOVERNANCE_OWNER_SLOT_MISMATCH")
        address = owner["address_base58"]
        if not address.startswith("T") or not 33 <= len(address) <= 35 or address == WALLET:
            raise RuntimeError("TEST_GOVERNANCE_OWNER_ADDRESS_INVALID")
        addresses.append(address)
        key_path = signer_dir / ("owner-" + str(i) + ".key")
        assert_file(key_path)
        if key_path.stat().st_size != 32:
            raise RuntimeError("TEST_GOVERNANCE_OWNER_KEY_SIZE_MISMATCH")
    if len(set(addresses)) != 3:
        raise RuntimeError("DUPLICATE_TEST_GOVERNANCE_OWNERS")
    return hashlib.sha256(":".join(addresses).encode()).hexdigest()


def get_shasta_account(path):
    payload = json.dumps({"address": WALLET, "visible": True}).encode("ascii")
    request = urllib.request.Request(
        BASE + path, data=payload, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=18) as response:
        obj = json.load(response)
    if not isinstance(obj, dict) or obj.get("Error"):
        raise RuntimeError("SHASTA_RPC_INVALID_RESPONSE")
    address = obj.get("address")
    if address is not None and address != WALLET:
        raise RuntimeError("SHASTA_RPC_WRONG_ACCOUNT")
    raw_balance = obj.get("balance", 0)
    if isinstance(raw_balance, bool) or not isinstance(raw_balance, int) or raw_balance < 0:
        raise RuntimeError("SHASTA_RPC_INVALID_BALANCE")
    return {"account_present": bool(address), "balance_sun": raw_balance}


def classify(latest, solid):
    if not latest["account_present"] or not solid["account_present"]:
        return "UNFUNDED" if not latest["balance_sun"] and not solid["balance_sun"] else "UNVERIFIED"
    if latest["balance_sun"] > 0 and solid["balance_sun"] > 0:
        return "FUNDED_AWAITING_DEPLOYMENT_APPROVAL"
    if latest["balance_sun"] == solid["balance_sun"] == 0:
        return "UNFUNDED"
    return "UNVERIFIED"


def run_self_test():
    z = {"account_present": False, "balance_sun": 0}
    f = {"account_present": True, "balance_sun": 2_000_000}
    a = {"account_present": True, "balance_sun": 0}
    assert classify(z, z) == "UNFUNDED"
    assert classify(f, f) == "FUNDED_AWAITING_DEPLOYMENT_APPROVAL"
    assert classify(f, a) == "UNVERIFIED"
    assert classify(a, a) == "UNFUNDED"
    assert classify(z, f) == "UNVERIFIED"
    print("MOJ1_SHASTA_WATCH_SELF_TEST=PASS")


def record_receipt(receipt):
    assert_dir(MONITOR)
    latest_file = MONITOR / "latest.json"
    history_file = MONITOR / "history.jsonl"
    temp_file = MONITOR / ("latest." + str(os.getpid()) + ".tmp")
    fd = os.open(temp_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(receipt, out, sort_keys=True, separators=(",", ":"))
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        if latest_file.exists():
            assert_file(latest_file)
        os.replace(temp_file, latest_file)
        if history_file.exists():
            assert_file(history_file)
            if history_file.stat().st_size > 4_000_000:
                rotated = MONITOR / "history.previous.jsonl"
                if rotated.exists():
                    assert_file(rotated)
                os.replace(history_file, rotated)
        fd = os.open(history_file, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as out:
            out.write(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n")
    finally:
        if temp_file.exists():
            temp_file.unlink()


def main():
    os.umask(0o077)
    if sys.argv[1:] == ["--self-test"]:
        run_self_test()
        return 0
    if sys.argv[1:]:
        raise SystemExit("Only --self-test is accepted")
    assert_dir(ROOT)
    assert_dir(MONITOR)
    lock_path = MONITOR / "watch.lock"
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "r+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
        receipt = {
            "timestamp_utc": timestamp,
            "network": "Shasta",
            "wallet": WALLET,
            "state": "UNVERIFIED",
            "public_owner_fingerprint": None,
            "latest": None,
            "solidified": None,
            "error_code": None,
            "private_key_content_read": False,
            "broadcast_count": 0,
            "mainnet_accessed": False,
            "deployment_performed": False,
        }
        try:
            receipt["public_owner_fingerprint"] = validate_public_state()
            receipt["latest"] = get_shasta_account("/wallet/getaccount")
            receipt["solidified"] = get_shasta_account("/walletsolidity/getaccount")
            receipt["state"] = classify(receipt["latest"], receipt["solidified"])
        except Exception as exc:
            receipt["error_code"] = type(exc).__name__ + ":" + str(exc)[:100]
        record_receipt(receipt)
        print(json.dumps(receipt, sort_keys=True))
        return 0 if receipt["state"] != "UNVERIFIED" else 2


if __name__ == "__main__":
    sys.exit(main())
