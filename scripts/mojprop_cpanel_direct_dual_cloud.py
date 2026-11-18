#!/usr/bin/env python3
"""MojPlayWin cPanel -> two encrypted Google Drive destinations, no disk spool.

This adapter does NOT auto-run. The Python API below requires an explicit,
explicit owner-approval value and real cloud / recovery preflight. The
ordinary command-line entrypoint is OFFLINE and READ-ONLY. No database names,
credentials, decrypted customer data, upload tokens or private keys are
accepted in argv or emitted to stdout.

Source: existing validated cPanel mariadb-dump/tar stream, executed through a
fingerprint-pinned SSH relay, with a trusted exact Git blob. Destination:
existing F01V2 AES-256-GCM/RSA-OAEP two-Drive chunk transfer and independent
per-object readback. Neither cPanel nor VPS receives a full plaintext or
encrypted backup file. The runner processes at most one bounded chunk.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess

# This hash is the immutable Git SHA-1 blob of the existing, reviewed 2026-11
# cPanel source program (not a hash of user data or of a DB password).
REVIEWED_SOURCE_BLOB = "7b330168b4ca1d597616e8724bc634910e769ea5"
SOURCE_FILE = "scripts/mojplaywin_backup_stream_cpanel.py"
OWNER_ARM = "OWNER_APPROVES_ONE_OFFSITE_BACKUP_SET_WITHOUT_DEPLOY"
SOURCE_MODES = frozenset(("mysql", "files"))
# Path and approved-alias provenance remain in the owner-pinned SSH config.
REQUIRED_HOST_ALIAS = "saeit-cpanel"
MAX_SOURCE_BLOB_BYTES = 65536
SSH_CONFIG_MAX_BYTES = 16000
SAFE_RUN = re.compile(r"factory-current-[0-9a-f]{32}\Z")
REMOTE_LAUNCH = (
    "import base64,sys;"
    "code=base64.b64decode(sys.argv[1],validate=True);"
    "sys.argv=[sys.argv[0]]+sys.argv[2:];"
    'exec(compile(code,"<reviewed-cpanel-backup-source>","exec"))'
)


class BackupHold(RuntimeError):
    """Fixed non-sensitive reason. A hold is not a successful backup."""


@dataclass(frozen=True)
class SourceAdmission:
    mode: str
    source_blob_verified: bool
    pinned_ssh_config_owner_only: bool
    source_bytes_written_to_runner_disk: int = 0
    live_database_identity_proven: bool = False
    live_media_scope_proven: bool = False
    complete_current_backup_verified: bool = False


def _owner_file(path: Path, size_limit: int) -> bytes:
    if not path.is_absolute() or path.is_symlink():
        raise BackupHold("UNSAFE_LOCAL_PATH")
    try:
        st = path.stat()
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
                or st.st_nlink != 1 or st.st_mode & 0o077
                or not 0 < st.st_size <= size_limit):
            raise BackupHold("UNSAFE_OWNER_FILE")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as stream:
            observed = os.fstat(stream.fileno())
            if (observed.st_ino != st.st_ino or observed.st_dev != st.st_dev
                    or observed.st_size != st.st_size
                    or observed.st_uid != st.st_uid):
                raise BackupHold("CHANGED_OWNER_FILE")
            return stream.read(size_limit + 1)
    except (OSError, ValueError):
        raise BackupHold("OWNER_FILE_NOT_READABLE") from None


def _git_blob(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\x00" + data
    ).hexdigest()


def _source_bytes(path: Path) -> bytes:
    # Git checkout source is intentionally mode 0644 (not secret). Secure
    # private config files separately; pin the *whole* executable blob.
    if not path.is_absolute() or path.is_symlink():
        raise BackupHold("UNSAFE_SOURCE_PATH")
    try:
        stat_before = path.stat()
        if (not stat.S_ISREG(stat_before.st_mode)
                or stat_before.st_uid != os.geteuid()
                or not 0 < stat_before.st_size <= MAX_SOURCE_BLOB_BYTES):
            raise BackupHold("UNSAFE_SOURCE_IDENTITY")
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as fh:
            check = os.fstat(fh.fileno())
            if (check.st_ino, check.st_dev, check.st_size) != (
                    stat_before.st_ino, stat_before.st_dev, stat_before.st_size):
                raise BackupHold("SOURCE_CHANGED_DURING_READ")
            raw = fh.read(MAX_SOURCE_BLOB_BYTES + 1)
    except (OSError, ValueError):
        raise BackupHold("UNAVAILABLE_REVIEWED_SOURCE") from None
    if _git_blob(raw) != REVIEWED_SOURCE_BLOB:
        raise BackupHold("UNAPPROVED_CPANEL_EXPORTER_CHANGE")
    return raw


def _verify_pinned_host_key(path: Path, host_entry: str, fingerprint: str) -> None:
    """Validate the fixed owner-reviewed public key, not a fresh SSH keyscan.

    Missing, additional, or altered host keys hold before any source byte.
    """
    if not path.is_absolute() or path.is_symlink():
        raise BackupHold("UNSAFE_KNOWN_HOSTS_PATH")
    try:
        st = path.stat()
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
                or not 0 < st.st_size <= 8192):
            raise BackupHold("UNSAFE_PINNED_HOST_FILE")
        text = path.read_text("ascii").strip()
        lines = [x.strip() for x in text.splitlines() if x.strip()]
        if (len(lines) != 1 or len(lines[0].split()) != 3
                or lines[0].split()[0] != host_entry
                or lines[0].split()[1] not in ("ssh-rsa", "ssh-ed25519")):
            raise BackupHold("UNEXPECTED_PINNED_SSH_PUBLIC_KEY")
        response = subprocess.run(
            ["ssh-keygen", "-lf", str(path), "-E", "sha256"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=5, check=False,
        )
        if (response.returncode != 0 or
                len(response.stdout) > 512 or
                fingerprint not in response.stdout.decode("ascii").split()):
            raise BackupHold("PINNED_SSH_FINGERPRINT_MISMATCH")
    except (OSError, UnicodeError, subprocess.TimeoutExpired):
        raise BackupHold("PINNED_SSH_FINGERPRINT_UNAVAILABLE") from None


def _assert_private_ssh_key(path_text: str) -> None:
    path = Path(path_text)
    if not path.is_absolute() or path.is_symlink():
        raise BackupHold("UNSAFE_SSH_IDENTITY_PATH")
    try:
        st = path.stat()
    except OSError:
        raise BackupHold("MISSING_SSH_IDENTITY_FILE") from None
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
            or st.st_nlink != 1 or st.st_mode & 0o077
            or not 100 <= st.st_size <= 16384):
        raise BackupHold("UNSAFE_SSH_PRIVATE_KEY_PERMISSIONS")


def _ssh_guard(config_path: Path) -> None:
    """Reject unsafe configuration constructs *without invoking ssh -G*.

    ssh -G can execute Match exec clauses; no untrusted config is evaluated.
    This guard is additional to a separate owner-established pinned-host-key
    identity attestation. Without that attestation the caller must not run.
    """
    raw = _owner_file(config_path, SSH_CONFIG_MAX_BYTES)
    try:
        text = raw.decode("ascii")
    except UnicodeError:
        raise BackupHold("INVALID_SSH_CONFIG") from None
    allowed = {
        "hostname", "user", "port", "identityfile", "userknownhostsfile",
        "proxyjump", "stricthostkeychecking", "identitiesonly", "batchmode",
        "connecttimeout", "connectionattempts", "serveraliveinterval",
        "serveralivecountmax", "forwardagent", "requesttty",
    }
    sections: dict[str, dict[str, str]] = {}
    current = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise BackupHold("INVALID_SSH_CONFIG_SYNTAX")
        name, value = parts[0].lower(), parts[1].strip()
        if name == "host":
            if (value not in (REQUIRED_HOST_ALIAS, "saeit-vps", "*")
                    or value in sections):
                raise BackupHold("UNEXPECTED_SSH_HOST_ALIAS")
            current = value
            sections[current] = {}
            continue
        if current is None or name not in allowed or name in sections[current]:
            raise BackupHold("UNSAFE_SSH_CONFIG_OPTION")
        if any(x in value for x in ("$", "`", ";", "\n", "\r", "%", "|")):
            raise BackupHold("DYNAMIC_SSH_CONFIG_VALUE")
        sections[current][name] = value
    if REQUIRED_HOST_ALIAS not in sections or "saeit-vps" not in sections:
        raise BackupHold("MISSING_EXPLICIT_SSH_HOST_BLOCK")

    # OpenSSH's *first matching value wins*: a leading Host * block may
    # shadow a more specific alias. Never pretend that a later value wins.
    def effective_for(alias):
        resolved = {}
        for match_name, options in sections.items():
            if match_name in (alias, "*"):
                for key, val in options.items():
                    resolved.setdefault(key, val)
        return resolved

    effective = effective_for(REQUIRED_HOST_ALIAS)
    relay = effective_for("saeit-vps")
    expected_primary = {
        "hostname": "178.239.147.125",
        "user": "zomorod2",
        "port": "1396",
        "proxyjump": "saeit-vps",
        "stricthostkeychecking": "yes",
        "identitiesonly": "yes",
        "batchmode": "yes",
        "forwardagent": "no",
    }
    expected_relay = {
        "hostname": "178.239.147.150",
        "user": "githubops",
        "port": "22",
        "stricthostkeychecking": "yes",
        "identitiesonly": "yes",
        "batchmode": "yes",
        "forwardagent": "no",
    }
    if any(effective.get(k, "").lower() != v
           for k, v in expected_primary.items()):
        raise BackupHold("SSH_IDENTITY_CONTRACT_MISMATCH")
    if any(relay.get(k, "").lower() != v
           for k, v in expected_relay.items()):
        raise BackupHold("SSH_RELAY_IDENTITY_CONTRACT_MISMATCH")
    if (relay.get("proxyjump") or
            effective.get("requesttty", "no").lower() != "no" or
            relay.get("requesttty", "no").lower() != "no"):
        raise BackupHold("NESTED_SSH_PROXY_OR_INTERACTIVE_TTY_DENIED")
    for ident in (effective, relay):
        for key in ("identityfile", "userknownhostsfile"):
            if not ident.get(key, "").startswith("/"):
                raise BackupHold("SSH_PINNED_IDENTITY_OR_KNOWN_HOSTS_MISSING")
    _verify_pinned_host_key(
        Path(effective["userknownhostsfile"]),
        "[178.239.147.125]:1396",
        "SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04",
    )
    _verify_pinned_host_key(
        Path(relay["userknownhostsfile"]),
        "178.239.147.150",
        "SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs",
    )
    _assert_private_ssh_key(effective["identityfile"])
    _assert_private_ssh_key(relay["identityfile"])


def admission(mode: str, *, source_path: Path, ssh_config: Path) -> SourceAdmission:
    if mode not in SOURCE_MODES:
        raise BackupHold("UNKNOWN_BACKUP_SCOPE")
    _source_bytes(source_path)
    _ssh_guard(ssh_config)
    return SourceAdmission(mode, True, True)


def build_producer_argv(mode: str, *, source_path: Path,
                        ssh_config: Path) -> list[str]:
    admission(mode, source_path=source_path, ssh_config=ssh_config)
    ssh = shutil.which("ssh")
    if ssh is None or not Path(ssh).is_absolute():
        raise BackupHold("SSH_CLIENT_NOT_AVAILABLE")
    encoded = base64.b64encode(_source_bytes(source_path)).decode("ascii")
    # SSH may invoke a remote shell, so the *only* interpolated input is
    # validated base64 code and one fixed source-mode value. No user strings.
    cmd = ("PYTHONDONTWRITEBYTECODE=1 python3 -B -c '"
           + REMOTE_LAUNCH + "' '" + encoded + "' '" + mode + "'")
    return [
        ssh, "-T", "-F", str(ssh_config),
        "-o", "StrictHostKeyChecking=yes",
        "-o", "BatchMode=yes",
        "-o", "ForwardAgent=no",
        REQUIRED_HOST_ALIAS, cmd,
    ]


def transfer_approved_scope(
        *, owner_approval: str, mode: str, source_path: Path,
        ssh_config: Path, verified_ssh_identity: bool,
        verified_passenger_database: bool, verified_complete_scope: bool,
        independently_recoverable_private_key: bool,
        store, gzip_executable: str, approved_public_pem: bytes,
        approved_public_spki_sha256: str,
        pseudonymous_owner_a: str, pseudonymous_owner_b: str,
        run_subdirectory: str):
    """Explicit no-scheduler entrypoint. All admission predicates fail closed.

    One mode per distinct 128-bit run namespace. This method neither creates
    a paid enrollment nor asserts that an isolated restore has been done.
    """
    if owner_approval != OWNER_ARM:
        raise BackupHold("EXPLICIT_ONE_TIME_APPROVAL_MISSING")
    if any(type(flag) is not bool or flag is not True for flag in (
            verified_ssh_identity, verified_passenger_database,
            verified_complete_scope, independently_recoverable_private_key)):
        raise BackupHold("UNPROVEN_PRODUCTION_OR_RECOVERY_PREREQUISITE")
    if type(run_subdirectory) is not str or not SAFE_RUN.fullmatch(run_subdirectory):
        raise BackupHold("UNSAFE_OR_REUSED_NAMESPACE")
    if (not isinstance(approved_public_pem, bytes)
            or not re.fullmatch("[0-9a-f]{64}", approved_public_spki_sha256)):
        raise BackupHold("UNVERIFIED_OWNER_RECOVERY_PUBLIC_KEY")
    from factory_dual_stream_v2 import _public_fingerprint
    _, observed_fingerprint = _public_fingerprint(approved_public_pem)
    if observed_fingerprint != approved_public_spki_sha256:
        raise BackupHold("WRONG_PUBLIC_RECOVERY_KEY")
    source_argv = build_producer_argv(
        mode, source_path=source_path, ssh_config=ssh_config,
    )
    if gzip_executable != "/usr/bin/gzip" or not Path(gzip_executable).is_file():
        raise BackupHold("UNAPPROVED_COMPRESSOR")
    if store.max_source_bytes > (48 * 1024**3 if mode == "mysql" else 12 * 1024**3):
        raise BackupHold("SOURCE_STREAM_EXCEEDS_CPANEL_SAFETY_CAP")
    # The referenced adapter checks two independent owner remotes, provider
    # quotas and private proof, then uploads and reads back every ciphertext
    # chunk; it only writes a completion manifest after successful true EOF.
    from factory_rclone_dual_parts import encrypt_verified_pipe_to_two_owner_drives
    result = encrypt_verified_pipe_to_two_owner_drives(
        store,
        vetted_producer_argv=source_argv,
        gzip_executable=gzip_executable,
        approved_public_pem=approved_public_pem,
        approved_public_spki_sha256=approved_public_spki_sha256,
        owner_pseudonym_a=pseudonymous_owner_a,
        owner_pseudonym_b=pseudonymous_owner_b,
        run_subdirectory=run_subdirectory,
    )
    return result


def readiness() -> dict:
    """Metadata-only: NEVER SSH, query providers or back up customer content."""
    src = Path(__file__).with_name("mojplaywin_backup_stream_cpanel.py")
    try:
        ok = _git_blob(src.read_bytes()) == REVIEWED_SOURCE_BLOB and not src.is_symlink()
    except OSError:
        ok = False
    return {
        "schema": "mojprop.cpanel.dual-cloud.readiness.v1",
        "reviewed_source_blob_present": ok,
        "capped_binary_streaming_implemented": True,
        "owner_approval_required": True,
        "two_distinct_oauth_remotes_verified": False,
        "provider_quota_verified": False,
        "ssh_runtime_authenticated": False,
        "key_offsite_recovery_proven": False,
        "current_backup_created": False,
        "restore_performed": False,
        "production_modified": False,
        "payment_created": False,
    }


if __name__ == "__main__":
    print(json.dumps(readiness(), sort_keys=True, separators=(",", ":")))
