#!/usr/bin/env python3
"""Pinned, fail-closed, direct-first cPanel read-only transport bootstrap.

Run only in the existing GitHub Actions runner with previously authorized SSH
secret environment variables VPS_KEY and HOST_KEY. This helper does not touch
the production website, database, wallet, mail, cron or cPanel files.

A blocked VPS:22 must not prevent a direct, correctly fingerprint-pinned
cPanel:1396 session. Never weaken StrictHostKeyChecking, never disclose keys.
Successful output is a ready SSH config at $RUNNER_TEMP/mpw-sales-audit-ssh/config.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

VPS_ADDR = "178.239.147.150"
VPS_RSAPIN = "SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs"
CPANEL_HOST = "zohal.pws-dns.net"
CPANEL_PORT = "1396"
CPANEL_EDPIN = "SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04"
MAX_ATTEMPTS = 2


class HostIdentityChanged(ValueError):
    pass


def _run(argv, *, timeout=25):
    try:
        return subprocess.run(argv, input=None, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, text=True,
                              check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _write_private(path, contents):
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf8") as handle:
            handle.write(contents)
    finally:
        os.chmod(path, 0o600)


def _key(raw, path):
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("SSH_KEY_NOT_CONFIGURED")
    normalized = raw.replace("\r\n", "\n").replace("\r", "").replace(
        "\\n", "\n").rstrip() + "\n"
    _write_private(path, normalized)
    verified = _run(["ssh-keygen", "-y", "-P", "", "-f", str(path)], timeout=8)
    if verified is None or verified.returncode != 0:
        raise ValueError("SSH_KEY_UNREADABLE")


def _pin_scanned(scanned, destination, expected):
    if not scanned or not scanned.strip():
        return False
    _write_private(destination, scanned)
    check = _run(["ssh-keygen", "-lf", str(destination), "-E", "sha256"], timeout=8)
    if check is None or check.returncode != 0:
        return False
    fingerprints = set()
    for line in check.stdout.splitlines():
        items = line.split()
        if len(items) < 2:
            return False
        fingerprints.add(items[1])
    if fingerprints != {expected}:
        raise HostIdentityChanged("PIN_MISMATCH_FAIL_CLOSED")
    return True


def _scan(host, port, keytype, destination, expected, *, via=None):
    for _ in range(MAX_ATTEMPTS):
        if via:
            argv = ["ssh", "-T", "-F", str(via), "saeit-vps",
                    "timeout 14s ssh-keyscan -T 8 -p " + port +
                    " -t " + keytype + " " + host]
            run = _run(argv, timeout=26)
        else:
            argv = ["ssh-keyscan", "-T", "8", "-p", port, "-t", keytype, host]
            run = _run(argv, timeout=12)
        if run is not None and run.returncode == 0 and run.stdout.strip():
            return _pin_scanned(run.stdout, destination, expected)
    return False


def _config(path, folder, *, via_vps):
    lines = [
        "Host saeit-cpanel",
        "  HostName " + CPANEL_HOST,
        "  User zomorod2",
        "  Port " + CPANEL_PORT,
        "  IdentityFile " + str(folder / "host.key"),
        "  UserKnownHostsFile " + str(folder / "host.known"),
    ]
    if via_vps:
        lines = [
            "Host saeit-vps",
            "  HostName " + VPS_ADDR,
            "  User githubops",
            "  Port 22",
            "  IdentityFile " + str(folder / "vps.key"),
            "  UserKnownHostsFile " + str(folder / "vps.known"),
        ] + lines
        lines.append("  ProxyJump saeit-vps")
    lines += [
        "Host *",
        "  StrictHostKeyChecking yes",
        "  BatchMode yes",
        "  IdentitiesOnly yes",
        "  ConnectTimeout 10",
        "  ConnectionAttempts 1",
        "  ForwardAgent no",
        "  RequestTTY no",
    ]
    _write_private(path, "\n".join(lines) + "\n")


def _cpanel_identity(config):
    check = _run(["ssh", "-T", "-F", str(config), "saeit-cpanel", "id -un"],
                 timeout=26)
    return check is not None and check.returncode == 0 and check.stdout.strip() == "zomorod2"


def main():
    home = os.environ.get("RUNNER_TEMP", "").strip()
    if not home or not pathlib.Path(home).is_dir():
        raise ValueError("RUNNER_TEMP_UNAVAILABLE")
    folder = pathlib.Path(home) / "mpw-sales-audit-ssh"
    folder.mkdir(mode=0o700, exist_ok=False)
    os.chmod(folder, 0o700)
    host_key = os.environ.get("HOST_KEY", "")
    vps_key = os.environ.get("VPS_KEY", "")
    _key(host_key, folder / "host.key")
    # The direct route must not depend on the VPS private key. Validate
    # that second identity only when the pinned direct route fails.
    config = folder / "config"
    cpanel_known = folder / "host.known"
    # First try the already-authorized hosting endpoint directly, using its
    # independently pinned ed25519 public identity.
    if _scan(CPANEL_HOST, CPANEL_PORT, "ed25519", cpanel_known, CPANEL_EDPIN):
        _config(config, folder, via_vps=False)
        if _cpanel_identity(config):
            print("MPW_CPANEL_ROUTE=DIRECT_PINNED_READONLY")
            return 0
        config.unlink()
        cpanel_known.unlink()
    # Direct route failed, so only the old pinned VPS jump may be attempted.
    _key(vps_key, folder / "vps.key")
    if not _scan(VPS_ADDR, "22", "rsa", folder / "vps.known", VPS_RSAPIN):
        print("MPW_CPANEL_ROUTE=VPS_PORT_22_UNREACHABLE_OR_NO_RSA")
        return 2
    _config(config, folder, via_vps=True)
    if not _scan(CPANEL_HOST, CPANEL_PORT, "ed25519", cpanel_known,
                 CPANEL_EDPIN, via=config):
        print("MPW_CPANEL_ROUTE=HOST_PORT_1396_UNREACHABLE_FROM_VPS")
        return 2
    # Rebuild config only after the cPanel host pin has been verified.
    if _cpanel_identity(config):
        print("MPW_CPANEL_ROUTE=VPS_PINNED_READONLY")
        return 0
    print("MPW_CPANEL_ROUTE=AUTHENTICATED_READONLY_SESSION_NOT_ESTABLISHED")
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except HostIdentityChanged:
        print("MPW_CPANEL_ROUTE=HOST_KEY_PIN_MISMATCH_FAIL_CLOSED")
        sys.exit(3)
    except (ValueError, OSError) as exc:
        print("MPW_CPANEL_ROUTE=SAFE_PREFLIGHT_FAILED_" + type(exc).__name__)
        sys.exit(4)
