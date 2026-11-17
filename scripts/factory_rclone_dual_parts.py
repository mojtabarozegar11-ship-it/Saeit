#!/usr/bin/env python3
"""Owner-only bounded rclone callbacks for F01V2 ciphertext parts.

This tool does NOT connect to databases, launch backups, accept credentials,
read application uploads, or automatically upload anything. It supplies the
real upload/read-back transport to factory_dual_stream_v2 after strict preflight.
No remote data deletion or intentional overwrite; cloud `rcat` itself does not provide an atomic no-overwrite guarantee.
"""
from __future__ import annotations

import configparser
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import select
import shutil
import stat
import subprocess
from dataclasses import dataclass

MAX_CONFIG_BYTES = 131072
MAX_CIPHER_PART_BYTES = 8 * 1024 * 1024 + 80
MAX_PROOF_BYTES = 8192
MAX_ABOUT_BYTES = 16384
MAX_DIR_LIST_BYTES = 262144
MAX_OBJECTS = 131072
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_USER_SOURCE_BYTES = 1 << 40
OBJECT = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,119}\Z")
REMOTE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
F01_MAGIC = b'F01V2\x00\x02'


class TransferHold(RuntimeError):
    """A non-sensitive fail-closed reason. Never include provider stderr."""


def _mode_secure_file(path: Path) -> bool:
    try:
        s = path.lstat()
    except OSError:
        return False
    return (path.is_absolute() and stat.S_ISREG(s.st_mode) and s.st_uid == os.geteuid()
            and s.st_nlink == 1 and not (s.st_mode & 0o077) and 0 < s.st_size <= MAX_CONFIG_BYTES)


def _safe_read_config(path: Path) -> configparser.RawConfigParser:
    if not _mode_secure_file(path):
        raise TransferHold('UNSAFE_OR_MISSING_OWNER_CONFIG')
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(fd, 'rb') as fh:
            s = os.fstat(fh.fileno())
            if s.st_uid != os.geteuid() or s.st_nlink != 1 or s.st_mode & 0o077:
                raise TransferHold('OWNER_CONFIG_CHANGED')
            raw = fh.read(MAX_CONFIG_BYTES + 1)
        if len(raw) != s.st_size:
            raise TransferHold('OWNER_CONFIG_CHANGED')
        conf = configparser.RawConfigParser(interpolation=None, strict=True)
        conf.read_string(raw.decode('utf-8'))
        return conf
    except (OSError, UnicodeError, configparser.Error):
        raise TransferHold('OWNER_CONFIG_UNREADABLE') from None


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _dedupe_pairs(pairs):
    record = {}
    for name, value in pairs:
        if name in record:
            raise ValueError('DUPLICATE_MANIFEST_FIELD')
        record[name] = value
    return record


def _validate_final_manifest(payload: bytes, name: str, parts: dict) -> bool:
    """Bind terminal marker to EVERY uploaded ciphertext object, not just filename.

    Structural parity is defense-in-depth; only the F01V2 cryptography core and
    a real independent restore can authenticate the MAC and GCM plaintext.
    """
    try:
        obj = json.loads(payload.decode('ascii'), object_pairs_hook=_dedupe_pairs)
        if type(obj) is not dict or set(obj) != {
                'schema','run_id','public_key_spki_sha256','wrapped_key',
                'nonce_prefix','chunk_limit','plain_total','cipher_total',
                'parts','owner_refs','source_consistency_external',
                'restore_verified','manifest_mac_sha256'}:
            return False
        if obj['schema'] != 'factory.dual-encrypted-stream.f01v2':
            return False
        run = obj['run_id']
        if type(run) is not str or not re.fullmatch(r'[0-9a-f]{32}', run):
            return False
        if name != 'f01v2-' + run + '-manifest.json':
            return False
        for key in ('public_key_spki_sha256','manifest_mac_sha256'):
            if type(obj[key]) is not str or not SHA256.fullmatch(obj[key]):
                return False
        if (obj['source_consistency_external'] is not False or
                obj['restore_verified'] is not False):
            return False
        if (type(obj['chunk_limit']) is not int or
                not 4096 <= obj['chunk_limit'] <= 8 * 1024 * 1024):
            return False
        if (type(obj['owner_refs']) is not list or len(obj['owner_refs']) != 2 or
                len(set(map(str,obj['owner_refs']))) != 2 or
                any(type(x) is not str or not re.fullmatch(r'[0-9a-f]{32}', x)
                    for x in obj['owner_refs'])):
            return False
        if (type(obj['wrapped_key']) is not str or
                not 100 <= len(obj['wrapped_key']) <= 8192 or
                type(obj['nonce_prefix']) is not str or
                not 10 <= len(obj['nonce_prefix']) <= 32):
            return False
        listed = obj['parts']
        if type(listed) is not list or not 1 <= len(listed) <= MAX_OBJECTS:
            return False
        if len(listed) != len(parts):
            return False
        total_cipher = total_plain = 0
        for idx, entry in enumerate(listed, 1):
            if type(entry) is not dict or set(entry) != {
                    'name','index','cipher_bytes','cipher_sha256','plain_bytes'}:
                return False
            expected_name = f'f01v2-{run}-{idx:06d}.enc'
            if (entry['name'] != expected_name or
                    type(entry['index']) is not int or entry['index'] != idx or
                    type(entry['cipher_bytes']) is not int or
                    type(entry['plain_bytes']) is not int or
                    not 1 <= entry['plain_bytes'] <= obj['chunk_limit'] or
                    entry['cipher_bytes'] != entry['plain_bytes'] + len(F01_MAGIC) + 41 or
                    type(entry['cipher_sha256']) is not str or
                    not SHA256.fullmatch(entry['cipher_sha256']) or
                    parts.get(expected_name) != (entry['cipher_bytes'], entry['cipher_sha256'])):
                return False
            total_cipher += entry['cipher_bytes']
            total_plain += entry['plain_bytes']
        if (type(obj['cipher_total']) is not int or
                type(obj['plain_total']) is not int or
                obj['cipher_total'] != total_cipher or
                obj['plain_total'] != total_plain):
            return False
        # F01V2's canonical exact byte serialization excludes ambiguous JSON
        # encodings and alternative manifest representations.
        canonical = json.dumps(obj,sort_keys=True,ensure_ascii=True,
                               separators=(',',':'),allow_nan=False).encode('ascii')
        return payload == canonical
    except (UnicodeError, ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return False


def _relative_path(path: str) -> bool:
    # Google Drive existing private proof folder names can contain spaces.
    # Arguments are passed as argv without shell interpretation.
    return (type(path) is str and 0 < len(path) <= 255
            and not path.startswith(('/', '.', '-')) and ':' not in path
            and all(part and part not in ('.', '..') and not part.startswith('-')
                    and not any(ord(c) < 32 or c == '\x7f' for c in part)
                    and not any(c in part for c in '\\')
                    for part in path.split('/')))


def _rclone_call(argv: list[str], *, input_bytes: bytes | None = None,
                 max_output: int = 0, timeout: int = 180) -> bytes:
    """No shell, bounded stdout, discard potentially sensitive stderr."""
    if not argv or not all(type(a) is str and a for a in argv):
        raise TransferHold('INVALID_RCLONE_ARGUMENTS')
    try:
        res = subprocess.run(
            argv, input=input_bytes, stdin=subprocess.DEVNULL if input_bytes is None else None,
            stdout=subprocess.PIPE if max_output else subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, check=False, timeout=timeout,
        )
        if res.returncode:
            raise TransferHold('RCLONE_PROVIDER_OPERATION_FAILED')
        raw = res.stdout or b''
        if len(raw) > max_output:
            raise TransferHold('RCLONE_OUTPUT_OVERSIZE')
        return raw
    except subprocess.TimeoutExpired:
        raise TransferHold('RCLONE_TIMEOUT') from None
    except FileNotFoundError:
        raise TransferHold('RCLONE_EXECUTABLE_MISSING') from None
    except (OSError, ValueError):
        raise TransferHold('RCLONE_PIPELINE_FAILURE') from None



@dataclass(frozen=True)
class RcloneAdmission:
    remote_a: str
    remote_b: str
    reserved_bytes_each: int
    free_a_before: int
    free_b_before: int
    distinct_private_roots: bool = True
    proof_readbacks_verified: bool = True
    current_backup_created: bool = False
    production_database_identity_proven: bool = False


class RcloneDualStore:
    """Provider-backed transport. Operator supplies verified remote config.

    Remote root_folder_id for A/B MUST be the already-owner-verified PRIVATE
    MOJ_FACTORY_BACKUPS_ENCRYPTED folder IDs. Each proof is a private, existing
    file that the other account cannot read because sharing is disabled.
    """
    def __init__(self, config_path: Path, *, remote_a: str, remote_b: str,
                 expected_root_a: str, expected_root_b: str, proof_path: str,
                 proof_sha256: str, max_source_bytes: int, chunk_bytes: int,
                 free_reserve_bytes: int, rclone_exe: str | None = None):
        if (not REMOTE.fullmatch(remote_a) or not REMOTE.fullmatch(remote_b)
                or remote_a == remote_b or expected_root_a == expected_root_b
                or not all(OBJECT.fullmatch(v) for v in (expected_root_a, expected_root_b))
                or not _relative_path(proof_path) or not SHA256.fullmatch(proof_sha256)):
            raise TransferHold('UNTRUSTED_REMOTE_IDENTITY_OR_PROOF')
        if (type(max_source_bytes) is not int or not 1 <= max_source_bytes <= MAX_USER_SOURCE_BYTES
                or type(chunk_bytes) is not int or not 4096 <= chunk_bytes <= 8 * 1024 * 1024
                or type(free_reserve_bytes) is not int or not 1 << 20 <= free_reserve_bytes <= 1 << 42):
            raise TransferHold('UNADMITTED_TRANSFER_SIZE')
        self.config_path = Path(config_path)
        self.remote_a, self.remote_b = remote_a, remote_b
        self.proof_path, self.proof_sha256 = proof_path, proof_sha256
        self.max_source_bytes, self.chunk_bytes = max_source_bytes, chunk_bytes
        self.free_reserve_bytes = free_reserve_bytes
        self.expected_root_a, self.expected_root_b = expected_root_a, expected_root_b
        self.executable = rclone_exe or shutil.which('rclone')
        if not self.executable or not Path(self.executable).is_absolute():
            raise TransferHold('RCLONE_NOT_INSTALLED')
        self._admission = None
        self._objects_written = set()
        self._callbacks_claimed = False
        # Independent per-provider ciphertext attestations; a final manifest
        # cannot precede dual upload AND exact bounded remote readback.
        self._cipher_parts = {self.remote_a: {}, self.remote_b: {}}
        self._verified_parts = {self.remote_a: set(), self.remote_b: set()}
        self._manifest_object_name = None
        self._manifest_payload_hash = None
        self._manifest_payload_len = None

    def _run(self, *argv: str, max_output: int = 0, input_bytes: bytes | None = None) -> bytes:
        return _rclone_call([self.executable, '--config', str(self.config_path), '--quiet', *argv],
                            max_output=max_output, input_bytes=input_bytes)

    def _about_free(self, remote: str) -> int:
        data = self._run('about', '--json', remote + ':', max_output=MAX_ABOUT_BYTES)
        try:
            parsed = json.loads(data)
            if type(parsed) is not dict or type(parsed.get('free')) is not int:
                raise ValueError()
            free = parsed['free']
            if free < 0 or free > 1 << 56:
                raise ValueError()
            return free
        except (ValueError, UnicodeError, TypeError):
            raise TransferHold('DRIVE_FREE_QUOTA_NOT_PROVEN') from None

    def _cat(self, remote: str, path: str, *, max_bytes: int) -> bytes:
        if not _relative_path(path) or not 1 <= max_bytes <= MAX_CIPHER_PART_BYTES + MAX_MANIFEST_BYTES:
            raise TransferHold('INVALID_READBACK_PATH_OR_SIZE')
        # head bounds output BEFORE subprocess read, avoiding unbounded pipes.
        return self._run('cat', remote + ':' + path, '--head', str(max_bytes + 1), max_output=max_bytes)

    def preflight(self) -> RcloneAdmission:
        if self._admission is not None:
            return self._admission
        conf = _safe_read_config(self.config_path)
        for remote, expected_root in ((self.remote_a, self.expected_root_a), (self.remote_b, self.expected_root_b)):
            if (not conf.has_section(remote) or conf.get(remote, 'type', fallback='') != 'drive'
                    or conf.get(remote, 'root_folder_id', fallback='') != expected_root
                    or not conf.get(remote, 'token', fallback='')):
                raise TransferHold('OWNER_DRIVE_REMOTE_CONFIG_UNVERIFIED')
        # OAuth tokens are read but NEVER printed or persisted by this script.
        token_a = conf.get(self.remote_a, 'token').encode('utf-8')
        token_b = conf.get(self.remote_b, 'token').encode('utf-8')
        if hmac.compare_digest(_sha(token_a), _sha(token_b)):
            raise TransferHold('SAME_OAUTH_CREDENTIALS_REJECTED')
        for remote in (self.remote_a, self.remote_b):
            observed = self._cat(remote, self.proof_path, max_bytes=MAX_PROOF_BYTES)
            if not hmac.compare_digest(_sha(observed), self.proof_sha256):
                raise TransferHold('PRIVATE_OWNER_PROOF_MISMATCH')
        a, b = self._about_free(self.remote_a), self._about_free(self.remote_b)
        # Strict worst-case part expansion: 8-byte MAGIC, run/seq/final/length
        # header + 16-byte GCM tag, per part; plus max manifest size.
        parts = (self.max_source_bytes + self.chunk_bytes - 1) // self.chunk_bytes
        if parts > MAX_OBJECTS:
            raise TransferHold('TOO_MANY_ADMITTED_PARTS')
        required = (self.max_source_bytes + parts * 64 + MAX_MANIFEST_BYTES
                    + self.free_reserve_bytes)
        if a < required or b < required:
            raise TransferHold('INSUFFICIENT_PROVIDER_VERIFIED_FREE_BYTES')
        self._admission = RcloneAdmission(self.remote_a, self.remote_b, required, a, b)
        return self._admission

    def _direct_child_names(self, remote: str, directory: str) -> set[str]:
        """Bounded provider-authoritative listing; never log names from Drive.

        A failure to read the current-backups folder is NOT evidence of an
        empty folder.  The caller must already have provisioned this private
        parent in the correct, owner-controlled Google Drive root.
        """
        if not _relative_path(directory):
            raise TransferHold('INVALID_REMOTE_DIRECTORY')
        output = self._run('lsf', remote + ':' + directory + '/',
                           '--format', 'p', max_output=MAX_DIR_LIST_BYTES)
        try:
            children = output.decode('utf-8').splitlines()
        except UnicodeError:
            raise TransferHold('REMOTE_NAMESPACE_LIST_UNREADABLE') from None
        if any(not x.rstrip('/') or '\x00' in x or '\r' in x or '/' in x.rstrip('/')
               for x in children):
            raise TransferHold('REMOTE_NAMESPACE_LIST_AMBIGUOUS')
        return {x.rstrip('/').casefold() for x in children}

    def callbacks(self, run_subdirectory: str):
        """Return four independent core callbacks (A upload/read, B upload/read).

        Caller MUST invoke preflight before any source stream opens. A new random
        run_subdirectory prevents accidental reuse; no remote cleanup ever runs.
        """
        if self._admission is None:
            raise TransferHold('MISSING_PROVIDER_PREFLIGHT')
        if not re.fullmatch(r'factory-current-[0-9a-f]{32}', run_subdirectory):
            raise TransferHold('UNSAFE_RUN_PREFIX')
        if self._callbacks_claimed:
            raise TransferHold('MULTIPLE_RUNS_ON_SAME_TRANSPORT_DENIED')
        # A failed, partially created namespace must never be silently reused.
        self._callbacks_claimed = True
        prefix = 'current-backups/' + run_subdirectory
        # Fail closed if either private Drive already has this run (even with
        # differently cased names). Listing failures are not 'empty' proofs.
        for remote in (self.remote_a, self.remote_b):
            if run_subdirectory.casefold() in self._direct_child_names(remote, 'current-backups'):
                raise TransferHold('BACKUP_RUN_NAMESPACE_ALREADY_EXISTS')
        # mkdir is additive, but NOT a Google-Drive-atomic create-if-absent.
        # A 128-bit owner-generated run ID plus list/check mitigates collisions.
        for remote in (self.remote_a, self.remote_b):
            self._run('mkdir', remote + ':' + prefix)
        for remote in (self.remote_a, self.remote_b):
            if self._direct_child_names(remote, prefix):
                raise TransferHold('NEW_BACKUP_RUN_NAMESPACE_NOT_EMPTY')

        def upload(remote: str, name: str, payload: bytes):
            if not OBJECT.fullmatch(name) or type(payload) is not bytes:
                raise TransferHold('INVALID_ENCRYPTED_PART')
            encrypted = name.endswith('.enc')
            manifest = name.endswith('-manifest.json')
            if not encrypted and not manifest:
                raise TransferHold('UNEXPECTED_UPLOAD_OBJECT')
            if encrypted and not (payload.startswith(F01_MAGIC) and 40 <= len(payload) <= MAX_CIPHER_PART_BYTES):
                raise TransferHold('PLAINTEXT_OR_OVERSIZED_PART_DENIED')
            if manifest and not 1 <= len(payload) <= MAX_MANIFEST_BYTES:
                raise TransferHold('INVALID_MANIFEST_BYTES')
            key = (remote, name)
            if key in self._objects_written:
                raise TransferHold('DUPLICATE_PART_UPLOAD')
            if encrypted and self._manifest_object_name is not None:
                raise TransferHold('CIPHERTEXT_AFTER_MANIFEST_DENIED')
            if manifest:
                parts_a = self._cipher_parts[self.remote_a]
                parts_b = self._cipher_parts[self.remote_b]
                if (not parts_a or parts_a != parts_b
                        or self._verified_parts[self.remote_a] != set(parts_a)
                        or self._verified_parts[self.remote_b] != set(parts_b)):
                    raise TransferHold('MANIFEST_BEFORE_DUAL_PART_READBACK_DENIED')
                if self._manifest_object_name is not None and self._manifest_object_name != name:
                    raise TransferHold('CONFLICTING_COMPLETION_MANIFEST_DENIED')
                if not _validate_final_manifest(payload, name, parts_a):
                    raise TransferHold('INVALID_OR_UNBOUND_COMPLETION_MANIFEST')
                if (self._manifest_payload_hash is not None and
                        (self._manifest_payload_len != len(payload) or
                         not hmac.compare_digest(self._manifest_payload_hash, _sha(payload)))):
                    raise TransferHold('TWO_DRIVES_MANIFEST_CONTENT_MISMATCH')
            path = prefix + '/' + name
            # Best-effort existence probe: rclone lsf on the whole folder; no
            # deletion or overwrite flags. Unique 128-bit run path is required.
            self._run('rcat', remote + ':' + path, '--size', str(len(payload)),input_bytes=payload)
            self._objects_written.add(key)
            if encrypted:
                self._cipher_parts[remote][name] = (len(payload), _sha(payload))
            else:
                self._manifest_object_name = name
                self._manifest_payload_hash = _sha(payload)
                self._manifest_payload_len = len(payload)

        def read(remote: str, name: str) -> bytes:
            if (remote, name) not in self._objects_written:
                raise TransferHold('UNUPLOADED_PART_READBACK_DENIED')
            max_bytes = MAX_MANIFEST_BYTES if name.endswith('-manifest.json') else MAX_CIPHER_PART_BYTES
            observed = self._cat(remote, prefix + '/' + name, max_bytes=max_bytes)
            if name.endswith('.enc'):
                expected = self._cipher_parts[remote].get(name)
                if (expected is None or len(observed) != expected[0]
                        or not hmac.compare_digest(_sha(observed), expected[1])):
                    raise TransferHold('REMOTE_CIPHERTEXT_READBACK_MISMATCH')
                self._verified_parts[remote].add(name)
            else:
                if (self._manifest_payload_len != len(observed) or
                        self._manifest_payload_hash is None or
                        not hmac.compare_digest(self._manifest_payload_hash, _sha(observed))):
                    raise TransferHold('REMOTE_MANIFEST_READBACK_MISMATCH')
            return observed

        return (lambda name,payload:upload(self.remote_a,name,payload),
                lambda name,payload:upload(self.remote_b,name,payload),
                lambda name:read(self.remote_a,name),
                lambda name:read(self.remote_b,name))


def runner_metadata_only(config: Path | None = None) -> dict:
    """No network, no read of OAuth token: safe for self-hosted CI diagnostics."""
    binary = shutil.which('rclone')
    path = config or (Path.home()/'.config/rclone/rclone.conf')
    return {
        'schema':'factory.rclone.runner-readiness.readonly.v1',
        'rclone_installed': bool(binary),
        'owner_local_config_secure_file_present':_mode_secure_file(path),
        'oauth_tokens_read':False,'provider_queried':False,
        'provider_free_quota_verified':False,
        'new_backup_created':False,'production_modified':False,
        'two_independent_remotes_verified':False,
    }


if __name__ == '__main__':
    print(json.dumps(runner_metadata_only(),sort_keys=True,separators=(',',':')))


class VerifiedGzipSource:
    """Pipelines one producer into gzip and verifies BOTH exit codes before EOF.

    The caller must supply a vetted executable/argv from an independently
    established source-identity and data-consistency admission process. This
    class has no DB credentials, no SQL defaults, no shell, no file writes.
    If the producer fails after emitting partial bytes, EOF raises; therefore
    the F01V2 core never publishes the terminal completion manifest.
    """
    def __init__(self, producer_argv: list[str], *, gzip_executable: str,
                 process_timeout: int = 3600):
        if (not isinstance(producer_argv, (list, tuple)) or not producer_argv
                or not all(type(v) is str and v for v in producer_argv)
                or type(gzip_executable) is not str
                or not gzip_executable.startswith('/')
                or type(process_timeout) is not int or not 60 <= process_timeout <= 86400):
            raise TransferHold('UNVETTED_SOURCE_PROCESS')
        self.producer_argv = list(producer_argv)
        self.gzip_executable = gzip_executable
        self.timeout = process_timeout
        self.producer = None
        self.compressor = None
        self.finished = False

    def __enter__(self):
        try:
            self.producer = subprocess.Popen(self.producer_argv,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, close_fds=True)
            self.compressor = subprocess.Popen([self.gzip_executable, '-c'],
                stdin=self.producer.stdout, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, close_fds=True)
            self.producer.stdout.close()
            return self
        except (OSError, ValueError):
            self._stop()
            raise TransferHold('VERIFIED_SOURCE_LAUNCH_FAILED') from None

    def _stop(self):
        for proc in (self.compressor, self.producer):
            if proc is not None and proc.poll() is None:
                proc.kill()
        for proc in (self.compressor, self.producer):
            if proc is not None:
                try: proc.wait(timeout=15)
                except subprocess.TimeoutExpired: pass

    def read(self, n: int = -1) -> bytes:
        if self.compressor is None or n <= 0 or n > 8 * 1024 * 1024:
            raise TransferHold('INVALID_STREAM_READ')
        if self.finished:
            return b''
        try:
            ready, _, _ = select.select([self.compressor.stdout], [], [], min(self.timeout, 120))
            if not ready:
                self._stop()
                raise TransferHold('BACKUP_SOURCE_STALLED')
            raw = os.read(self.compressor.stdout.fileno(), n)
            if raw:
                return raw
            # Critical: check upstream exit *before* signalling true EOF.
            gzip_rc = self.compressor.wait(timeout=self.timeout)
            producer_rc = self.producer.wait(timeout=self.timeout)
            if gzip_rc or producer_rc:
                raise TransferHold('BACKUP_SOURCE_OR_COMPRESSOR_FAILED')
            self.finished = True
            return b''
        except subprocess.TimeoutExpired:
            self._stop()
            raise TransferHold('BACKUP_SOURCE_WAIT_TIMEOUT') from None

    def __exit__(self, exc_type, exc, tb):
        if self.compressor is not None and self.compressor.stdout is not None:
            self.compressor.stdout.close()
        if exc_type or not self.finished:
            self._stop()
        return False


def encrypt_verified_pipe_to_two_owner_drives(store: RcloneDualStore, *,
        vetted_producer_argv: list[str], gzip_executable: str,
        approved_public_pem: bytes, approved_public_spki_sha256: str,
        owner_pseudonym_a: str, owner_pseudonym_b: str,
        run_subdirectory: str):
    """One source snapshot -> compressed bytes -> bounded AEAD parts -> TWO Drives.

    This is an **operator-invoked** low-level function, NOT a CLI that guesses
    which production database or media dirs to export. Preflight runs BEFORE
    the first source byte is requested. External owner approval/source identity
    and consistency gates are required; no background/scheduled live writes.
    """
    store.preflight()
    from factory_dual_stream_v2 import encrypt_stream_to_dual_stores
    cb_a, cb_b, rd_a, rd_b = store.callbacks(run_subdirectory)
    with VerifiedGzipSource(vetted_producer_argv,gzip_executable=gzip_executable) as source:
        return encrypt_stream_to_dual_stores(source,
            public_pem=approved_public_pem,
            trusted_public_spki_sha256=approved_public_spki_sha256,
            owner_a=owner_pseudonym_a,owner_b=owner_pseudonym_b,
            upload_a=cb_a,upload_b=cb_b,read_a=rd_a,read_b=rd_b,
            chunk_bytes=store.chunk_bytes,max_source_bytes=store.max_source_bytes)
