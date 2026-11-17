"""Conservative source-only Google Drive offsite backup quota feasibility for MOJ-PROP-01.

Do not mistake an empty Drive folder or connected Google account for available
quota, backup completeness, correct encryption or an independent restore.
All inputs are untrusted, collected outside this module. No OAuth, IO, network,
payments, database access, file creation or deployment.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
import re

MIB = 1024 ** 2
GIB = 1024 ** 3
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
MIN_RESERVE_BYTES = 512 * MIB
MAX_REASONABLE_SOURCE_BYTES = 200 * GIB


class OffsiteNotProven(ValueError):
    """No evidence-supported source-to-cloud capacity admission."""


def _require(value: bool, reason: str) -> None:
    if not value:
        raise OffsiteNotProven(reason)


def _bytes(value: object, field: str) -> int:
    _require(type(value) is int and 0 < value <= MAX_REASONABLE_SOURCE_BYTES,
             field + " requires exact positive bytes")
    return value


@dataclass(frozen=True)
class OwnerDriveSnapshot:
    source_commit: str
    quota_checked_at: str
    source_db_estimate_bytes: int
    source_app_bytes: int
    source_media_bytes: int
    google_drive_quota_free_bytes: int
    google_drive_quota_total_bytes: int
    reserve_bytes: int
    account_private: bool
    app_and_media_inventory_complete: bool
    quota_from_authenticated_owner_api: bool
    destination_not_cpanel_or_vps: bool
    owner_folder_access_verified: bool
    encrypted_before_upload: bool
    independent_key_recovery_verified: bool
    multipart_resumable_verified: bool

    def screen(self, *, expected_commit: str, now: datetime) -> dict:
        """Pure mathematical screen only, always denies production release."""
        _require(type(expected_commit) is str and bool(SHA40.fullmatch(expected_commit)),
                 "exact release SHA required")
        _require(type(self.source_commit) is str and
                 self.source_commit == expected_commit,
                 "pinned source commit differs")
        try:
            checked = datetime.fromisoformat(self.quota_checked_at.replace("Z", "+00:00"))
        except (AttributeError, ValueError) as exc:
            raise OffsiteNotProven("invalid Drive quota timestamp") from exc
        _require(checked.tzinfo is not None and checked.utcoffset() is not None,
                 "quota evidence timezone required")
        _require(isinstance(now, datetime) and now.tzinfo is not None and
                 now.utcoffset() is not None, "current trusted time missing")
        age = now.astimezone(timezone.utc) - checked.astimezone(timezone.utc)
        _require(timedelta(0) <= age <= timedelta(minutes=15),
                 "Drive quota measurement too old or future")
        db = _bytes(self.source_db_estimate_bytes, "source database estimate")
        app = _bytes(self.source_app_bytes, "application archive")
        media = _bytes(self.source_media_bytes, "media archive")
        free = _bytes(self.google_drive_quota_free_bytes, "owner Drive free quota")
        total = _bytes(self.google_drive_quota_total_bytes, "owner Drive total quota")
        reserve = _bytes(self.reserve_bytes, "independent headroom")
        _require(reserve >= MIN_RESERVE_BYTES, "insufficient reserve")
        _require(free <= total, "Drive quota larger than total")
        for key in ("account_private", "app_and_media_inventory_complete",
                    "quota_from_authenticated_owner_api",
                    "destination_not_cpanel_or_vps", "owner_folder_access_verified",
                    "encrypted_before_upload", "independent_key_recovery_verified",
                    "multipart_resumable_verified"):
            _require(getattr(self, key) is True, key + " unverified")
        # Two conservative database snapshots, one full app/media set and reserve.
        # These are *screening* lower bounds, not proof actual compressed sizes.
        required = 2 * db + app + media + reserve
        _require(free >= required, "Drive free quota does not meet conservative requirement")
        return {
            "product": "MOJ-PROP-01",
            "provider": "google_drive",
            "source_commit": expected_commit,
            "minimum_screened_bytes": required,
            "claimed_provider_quota_free_bytes": free,
            "capacity_math_screen_passed": True,
            "quota_authenticated_by_this_process": False,
            "backup_uploaded_verified": False,
            "encrypted_backup_roundtrip_verified": False,
            "isolated_db_app_media_restore_verified": False,
            "legal_and_broker_gates_verified": False,
            "lead_registration_authorized": False,
            "deployment_authorized": False,
            "payment_authorized": False,
        }
