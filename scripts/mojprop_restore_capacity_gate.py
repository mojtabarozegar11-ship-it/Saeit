"""Conservative, source-only Moj Prop isolated-restore capacity gate.

No host probes, filesystem writes, database queries, or release side effects.
All values must be independently measured in bytes on the intended storage
target; rounded ranges or an unverified remote VPS are NOT acceptable.
"""
from __future__ import annotations

from dataclasses import dataclass

MIB = 1024 * 1024


class CapacityNotProven(ValueError):
    """Release must remain blocked without measured independent capacity."""


@dataclass(frozen=True)
class RestoreCapacity:
    live_database_bytes: int
    app_media_bytes: int
    destination_free_bytes: int
    headroom_bytes: int
    independent_destination: bool
    encrypted_private_storage: bool
    isolated_restore_supported: bool

    def required_bytes(self) -> int:
        """Two complete DB snapshots plus app/media and reserved headroom."""
        values = (
            self.live_database_bytes,
            self.app_media_bytes,
            self.destination_free_bytes,
            self.headroom_bytes,
        )
        if any(type(value) is not int or value <= 0 for value in values):
            raise CapacityNotProven("positive exact byte measurements required")
        if any(type(value) is not bool for value in (
            self.independent_destination,
            self.encrypted_private_storage,
            self.isolated_restore_supported,
        )):
            raise CapacityNotProven("explicit independent restore controls required")
        if not all((
            self.independent_destination,
            self.encrypted_private_storage,
            self.isolated_restore_supported,
        )):
            raise CapacityNotProven("independent encrypted isolated restore unproven")
        return 2 * self.live_database_bytes + self.app_media_bytes + self.headroom_bytes

    def verify(self) -> int:
        required = self.required_bytes()
        if self.destination_free_bytes < required:
            raise CapacityNotProven(
                "insufficient measured destination capacity for independent restore"
            )
        return self.destination_free_bytes - required
