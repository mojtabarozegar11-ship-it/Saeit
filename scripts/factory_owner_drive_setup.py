#!/usr/bin/env python3
"""Owner-interactive, local-only setup of two independently granted rclone Drives.

Run over a trusted interactive SSH shell, NEVER in CI or a chat tool.
No OAuth tokens, rclone config bytes, password, or provider stderr are printed
by this wrapper. Rclone's own interactive configurator runs on the owner TTY.
The script will not upload data, export SQL, delete objects, or deploy software.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

from factory_rclone_ephemeral_binary import provision_verified_rclone
from factory_rclone_dual_parts import RcloneDualStore, TransferHold, _mode_secure_file, MAX_MANIFEST_BYTES, _safe_read_config

ROOT_A = '191sAkv4A01S9o6zhx-vM5xM7WO31qHPn'
ROOT_B = '1e6D3Ek4k-4JT_oyEoiY_JejErZFssrC_'
PRIVATE_PROOF = 'F-01 Factory VPS encrypted recovery 2026-10-30/factory-runtime-001.f01enc.seg-21'
PROOF_SHA = '06098cc64e9f1ac23670ac8d2f71e4402e668940b9a00c77a3184b1aec0e5b30'


def _secure_config_directory(home: Path) -> Path:
    # Only work under the actual invoking OS user's home, never a supplied path.
    if not home.is_absolute() or home.is_symlink() or home != Path.home():
        raise TransferHold('OWNER_HOME_UNTRUSTED')
    base = home / '.config'
    confdir = base / 'rclone'
    for directory in (base, confdir):
        if directory.is_symlink():
            raise TransferHold('CONFIG_PATH_SYMLINK_DENIED')
        if not directory.exists():
            directory.mkdir(mode=0o700)
        st = directory.lstat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid():
            raise TransferHold('OWNER_CONFIG_DIRECTORY_NOT_OWNED')
        # ~/.config is commonly 0755; do not change permissions of other apps.
        # Only ~/.config/rclone MUST be private (0700).
        if directory == confdir and (st.st_mode & 0o077):
            raise TransferHold('OWNER_RCLONE_DIRECTORY_NOT_PRIVATE')
        if st.st_mode & 0o020:
            raise TransferHold('OWNER_CONFIG_DIRECTORY_GROUP_WRITABLE')
    config = confdir / 'rclone.conf'
    if config.exists() or config.is_symlink():
        if not _mode_secure_file(config):
            raise TransferHold('EXISTING_CONFIG_UNSAFE_OR_SHARED')
    return config


HISTORICAL_SNAPSHOT_BYTES = 1408634880
HISTORICAL_CHUNK_BYTES = 8 * 1024 * 1024
HISTORICAL_FREE_RESERVE_BYTES = 1024 ** 3


def historical_pair_required_bytes() -> int:
    # Two separate logical raw archives, each with its own manifest and
    # worst-case per-part ciphertext overhead; reserve is held once.
    parts = (HISTORICAL_SNAPSHOT_BYTES + HISTORICAL_CHUNK_BYTES - 1) // HISTORICAL_CHUNK_BYTES
    return (2 * (HISTORICAL_SNAPSHOT_BYTES + parts * 64 + MAX_MANIFEST_BYTES)
            + HISTORICAL_FREE_RESERVE_BYTES)


def _validate_owner_oauth_config(config: Path) -> None:
    """Reject default client, non-refreshable tokens and duplicate grants.
    
    Configuration validation alone cannot prove Google's publishing state,
    user identity, provider capacity, or successful live authorization.
    Never print config fields or credentials.
    """
    conf = _safe_read_config(config)
    refresh_tokens = []
    for remote, root in (("factory_a", ROOT_A), ("factory_b", ROOT_B)):
        if (not conf.has_section(remote)
                or conf.get(remote, "type", fallback="") != "drive"
                or conf.get(remote, "root_folder_id", fallback="") != root):
            raise TransferHold("OWNER_DRIVE_REMOTE_CONFIG_UNVERIFIED")
        client_id = conf.get(remote, "client_id", fallback="")
        client_secret = conf.get(remote, "client_secret", fallback="")
        if (not re.fullmatch(r"[A-Za-z0-9_-]{8,180}\.apps\.googleusercontent\.com", client_id)
                or not client_secret.strip()):
            raise TransferHold("OWNER_DEDICATED_GOOGLE_OAUTH_CLIENT_REQUIRED")
        if (conf.get(remote, "scope", fallback="") != "drive"
                or conf.get(remote, "service_account_file", fallback="")
                or conf.get(remote, "service_account_credentials", fallback="")
                or conf.get(remote, "team_drive", fallback="")):
            raise TransferHold("OWNER_EXISTING_PRIVATE_DRIVE_SCOPE_REQUIRED")
        try:
            token = json.loads(conf.get(remote, "token", fallback=""))
            refresh = token.get("refresh_token") if isinstance(token, dict) else None
            if not isinstance(refresh, str) or not refresh.strip():
                raise ValueError()
        except (ValueError, TypeError):
            raise TransferHold("OWNER_OFFLINE_REFRESH_GRANT_REQUIRED") from None
        refresh_tokens.append(refresh)
    if refresh_tokens[0] == refresh_tokens[1]:
        raise TransferHold("DUPLICATE_OAUTH_REFRESH_GRANT_DENIED")


def _check(executable: Path, config: Path) -> dict:
    # This is connectivity+quota observation only, NOT current-source admission.
    # No database is accessed and no cloud object is created.
    _validate_owner_oauth_config(config)
    preflight = RcloneDualStore(
        config,
        remote_a='factory_a', remote_b='factory_b',
        expected_root_a=ROOT_A, expected_root_b=ROOT_B,
        proof_path=PRIVATE_PROOF, proof_sha256=PROOF_SHA,
        max_source_bytes=1, chunk_bytes=4096,
        free_reserve_bytes=1 << 30,
        rclone_exe=str(executable),
    ).preflight()
    pair_required = historical_pair_required_bytes()
    # Do not turn a 1GiB connectivity signal into a claim of pair admission.
    # The transfer itself still rechecks each actual destination before opening bytes.
    pair_capacity = (preflight.free_a_before >= pair_required
                     and preflight.free_b_before >= pair_required)
    return {
        'schema': 'factory.owner-private-oauth-connectivity.v2',
        'owner_interactive_shell_required': True,
        'distinct_private_drives_verified': True,
        'dedicated_client_and_distinct_refresh_grants_present': True,
        'google_oauth_publishing_state_verified': False,
        'existing_private_proof_readback_verified': preflight.proof_readbacks_verified,
        'free_bytes_drive_a': preflight.free_a_before,
        'free_bytes_drive_b': preflight.free_b_before,
        'provider_quota_minimum_1GiB_verified': True,
        'historical_pair_required_bytes_each_drive': pair_required,
        'historical_pair_capacity_screen_passed': pair_capacity,
        'historical_pair_uploaded': False,
        'historical_pair_independent_restore_verified': False,
        'current_factory_size_admitted': False,
        'current_mysql_consistency_proven': False,
        'complete_media_scope_proven': False,
        'current_backup_created': False,
        'production_modified': False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Owner-only dual Google Drive one-time authorization + sanitized read-only admission')
    parser.add_argument('--configure', action='store_true', help='Interactively configure factory_a and factory_b in a trusted TTY')
    opts = parser.parse_args(argv)
    # Never call OAuth setup through Actions, non-interactive shells, or logs.
    if os.geteuid() == 0 or not sys.stdin.isatty() or not sys.stdout.isatty() or os.environ.get('GITHUB_ACTIONS'):
        print('HOLD: TRUSTED_OWNER_INTERACTIVE_TERMINAL_REQUIRED', file=sys.stderr)
        return 2
    old_umask = os.umask(0o077)
    try:
        config = _secure_config_directory(Path.home())
        with tempfile.TemporaryDirectory(prefix='owner-oauth-bootstrap-', dir='/tmp') as tmp:
            with provision_verified_rclone(Path(tmp)) as exe:
                if opts.configure:
                    print('Owner terminal only. Configure TWO separate Google accounts as factory_a / factory_b.')
                    print('Use your OWN OAuth desktop client ID; shared client retirement is in 2026. Select scope drive; restrict each root_folder_id to its verified private root.')
                    print('Do not screen-record or forward any rclone config output; rclone may display sensitive tokens.')
                    rc = subprocess.run([str(exe), '--config', str(config), 'config'], stdin=None, stdout=None, stderr=None, check=False).returncode
                    if rc:
                        raise TransferHold('OWNER_RCLONE_CONFIG_NOT_COMPLETED')
                if not _mode_secure_file(config):
                    raise TransferHold('OWNER_CONFIG_MISSING_OR_UNSAFE_AFTER_SETUP')
                result = _check(exe, config)
                print('FACTORY_DRIVE_CONNECTIVITY=' + json.dumps(result, sort_keys=True, separators=(',', ':')))
            if not result['historical_pair_capacity_screen_passed']:
                print('HOLD: HISTORICAL_PAIR_FREE_QUOTA_INSUFFICIENT', file=sys.stderr)
                return 2
        return 0
    except (TransferHold, OSError, ValueError) as exc:
        # Never print raw traceback/provider stderr or config values.
        code = str(exc) if type(exc) is TransferHold else 'OWNER_SETUP_OR_PROVIDER_GATE_FAILED'
        print('HOLD: ' + code, file=sys.stderr)
        return 2
    finally:
        os.umask(old_umask)


if __name__ == '__main__':
    raise SystemExit(main())
