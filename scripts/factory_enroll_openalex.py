#!/usr/bin/env python3
"""One-shot, owner-authorized OpenAlex enrollment on the private factory VPS.

The returned credential is NEVER sent to a GitHub runner or printed to logs.
Its activation is controlled by the owner through the OpenAlex email link.
"""
import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import urllib.error
import urllib.request

URL = "https://api.openalex.org/api-keys"
KEY_PATTERN = re.compile(r"[A-Za-z0-9_-]{16,200}\Z")
EMAIL_PATTERN = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+\Z")

def safe_destination(destination):
    parent = destination.parent
    if parent.is_symlink() or not parent.is_dir():
        raise RuntimeError("OPENALEX_PRIVATE_PARENT_INVALID")
    info = parent.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o022:
        raise RuntimeError("OPENALEX_PRIVATE_PARENT_PERMISSIONS")
    if destination.is_symlink():
        raise RuntimeError("OPENALEX_CREDENTIAL_SYMLINK")
    if destination.exists():
        current = destination.stat()
        if (not stat.S_ISREG(current.st_mode) or current.st_uid != os.getuid()
                or current.st_mode & 0o077):
            raise RuntimeError("OPENALEX_EXISTING_CREDENTIAL_UNSAFE")
        return False
    return True

def enroll(email, destination, fetch=None):
    if not EMAIL_PATTERN.fullmatch(email) or len(email) > 254:
        raise ValueError("OPENALEX_INVALID_OWNER_EMAIL")
    if not safe_destination(destination):
        return "ALREADY_CONFIGURED"
    if fetch is None:
        fetch = urllib.request.urlopen
    body = json.dumps({"email": email, "name": "Mojtaba Roozegar",
                       "agent": "Codex factory agriculture research"}).encode("utf-8")
    req = urllib.request.Request(
        URL, data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Accept": "application/json",
                 "User-Agent": "SaeitFactoryResearchEnrollment/1.0"})
    try:
        with fetch(req, timeout=25) as response:
            status = response.status
            raw = response.read(16385)
        if status != 201 or len(raw) > 16384:
            return "PROVIDER_UNEXPECTED_RESPONSE"
        packet = json.loads(raw)
    except urllib.error.HTTPError as exc:
        if exc.code == 409:
            try:
                info = json.loads(exc.read(2048))
            except (ValueError, UnicodeError):
                return "PROVIDER_CONFLICT"
            if info.get("error") == "account_exists" or info.get("code") == "account_exists":
                return "ACCOUNT_ALREADY_EXISTS"
            if info.get("error") == "activation_pending" or info.get("code") == "activation_pending":
                return "ACTIVATION_ALREADY_PENDING"
            return "PROVIDER_CONFLICT"
        if exc.code == 429:
            return "PROVIDER_REGISTRATION_RATE_LIMITED"
        return "PROVIDER_HTTP_ERROR_" + str(exc.code)
    except (urllib.error.URLError, TimeoutError, OSError):
        return "PROVIDER_NETWORK_UNAVAILABLE"
    except (ValueError, UnicodeError):
        return "PROVIDER_BAD_RESPONSE"
    if not isinstance(packet, dict):
        return "PROVIDER_BAD_RESPONSE"
    key = packet.get("api_key")
    if (not isinstance(key, str) or not KEY_PATTERN.fullmatch(key)
            or packet.get("email") != email
            or packet.get("status") not in ("pending_activation", "active")):
        return "PROVIDER_UNEXPECTED_KEY_RESPONSE"
    # Use a same-directory atomic hard link: concurrent enrollment cannot
    # overwrite a credential, and crash/partial-write cannot publish a key.
    handle, name = tempfile.mkstemp(prefix=".openalex-registration-", dir=destination.parent)
    try:
        os.fchmod(handle, 0o600)
        with os.fdopen(handle, "w", encoding="ascii") as stream:
            stream.write(key + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(name, destination, follow_symlinks=False)
        except FileExistsError:
            if not safe_destination(destination):
                return "ALREADY_CONFIGURED"
            raise
    finally:
        os.unlink(name)
    return "EMAIL_ACTIVATION_REQUIRED" if packet["status"] == "pending_activation" else "ACTIVE_KEY_INSTALLED"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--credential-dir", required=True)
    args = parser.parse_args()
    target = Path(args.credential_dir).expanduser().resolve() / ".openalex-api-key"
    result = enroll(args.email, target)
    print("FACTORY_OPENALEX_ENROLLMENT_STATUS=" + result)
    print("FACTORY_OPENALEX_SECRET_IN_CI_LOGS=false")
    if result not in ("ALREADY_CONFIGURED", "EMAIL_ACTIVATION_REQUIRED",
                      "ACTIVE_KEY_INSTALLED", "ACTIVATION_ALREADY_PENDING",
                      "ACCOUNT_ALREADY_EXISTS"):
        raise SystemExit(2)

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # No API response bodies, token contents, network URL, or user email.
        print("FACTORY_OPENALEX_ENROLLMENT_FAILED=" + type(error).__name__,
              file=sys.stderr)
        raise SystemExit(1)
