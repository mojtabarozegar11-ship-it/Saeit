"""Source-owned, fail-closed PICM retirement policy for public route audits.

The owner's existing E7 manifest retires PICM and excludes it from the
active deployment/continuity queue. This does not delete files, redirect a
site, open old login URLs or claim the site works. Unreviewed changes to
the manifest fail closed instead of silently dropping other children.
"""
from __future__ import annotations

import json
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[1] / "runtime/retired_picm_manifest.json"
RETIRED_PATHS = frozenset(("/picm/", "/picm/login/"))
MAX_MANIFEST_BYTES = 16_384
_EXPECTED_EXECUTION = {
    "reactivate": False,
    "deploy": False,
    "rebuild": False,
    "delete_source_without_explicit_scope": False,
}


class RetirementPolicyUnavailable(RuntimeError):
    pass


def assert_retired_picm_manifest(path: Path = MANIFEST) -> None:
    """Validate exactly this owner's recorded retirement, or refuse audit."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise RetirementPolicyUnavailable("retired PICM manifest missing or linked")
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_MANIFEST_BYTES + 1)
        if len(raw) > MAX_MANIFEST_BYTES:
            raise RetirementPolicyUnavailable("retired PICM manifest too large")
        obj = json.loads(raw)
    except (OSError, ValueError, UnicodeError) as exc:
        raise RetirementPolicyUnavailable("invalid retired PICM manifest") from exc
    if (type(obj) is not dict or obj.get("version") != 1
            or type(obj.get("version")) is not int
            or obj.get("name") != "PICM"
            or obj.get("status") != "retired"
            or obj.get("policy") != "excluded_from_active_queue"
            or type(obj.get("execution_policy")) is not dict
            or obj["execution_policy"] != _EXPECTED_EXECUTION):
        raise RetirementPolicyUnavailable("PICM retirement does not match owner policy")


def assert_no_retired_routes(active_paths) -> None:
    """Both probes must exclude the exact disabled entry and login path."""
    if any(route in RETIRED_PATHS for route in active_paths):
        raise RetirementPolicyUnavailable("retired PICM route was reactivated in audit")
