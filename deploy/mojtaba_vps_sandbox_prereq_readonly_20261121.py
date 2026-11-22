#!/usr/bin/env python3
"""VPS-only, no-change census of security prerequisites for the canonical bot.

May run only as existing githubops, through the already pinned VPS SSH relay.
Never creates a namespace, launches a model/worker, connects to a database,
changes sysctl/AppArmor, reads environment values, or exposes command lines.
A capability hint is NOT proof that sandbox execution is safe.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import pwd
import re


SCHEMA = "mojtaba.bot.ai.vps-sandbox-prerequisites.readonly.v1"
HOME = Path("/home/githubops")
RUNTIME = HOME / "factory-runtime"

# Hard-coded, non-secret, read-only system metadata only.
KERNEL = {
    "max_user_namespaces": Path("/proc/sys/user/max_user_namespaces"),
    "unprivileged_userns_clone": Path("/proc/sys/kernel/unprivileged_userns_clone"),
    "apparmor_unprivileged_userns_restriction":
        Path("/proc/sys/kernel/apparmor_restrict_unprivileged_userns"),
}
CGROUP = {
    "memory_max": Path("/sys/fs/cgroup/memory.max"),
    "memory_current": Path("/sys/fs/cgroup/memory.current"),
    "cpu_max": Path("/sys/fs/cgroup/cpu.max"),
}
BINS = {
    "bwrap": Path("/usr/bin/bwrap"),
    "unshare": Path("/usr/bin/unshare"),
    "python3": Path("/usr/bin/python3"),
}
SOURCE = {
    "factory_runtime_root": RUNTIME,
    "django_canonical_host_adapter": RUNTIME / "django-app/core/mojtaba_host_runtime.py",
    "ava_inert_core": RUNTIME / "django-app/ava_core/runtime.py",
}


def normalized_scalar(value: str, *, max_size: int = 64) -> str | None:
    """Accept numeric Linux limits or 'max', never arbitrary sysctl payloads."""
    if not isinstance(value, str) or len(value) > max_size:
        return None
    compact = " ".join(value.strip().split())
    # cgroup v2 cpu.max often uses "max 100000" for unbounded CPU.
    if compact == "max" or re.fullmatch(r"max [0-9]{1,24}", compact):
        return compact
    if re.fullmatch(r"[0-9]{1,24}(?: [0-9]{1,24})?", compact):
        return compact
    return None


def read_scalar(path: Path) -> str | None:
    try:
        if path.is_symlink() or not path.is_file():
            return None
        return normalized_scalar(path.read_text(encoding="ascii")[:70])
    except (OSError, UnicodeError, ValueError):
        return None


def regular_file_present(path: Path) -> bool:
    """Avoid following a symlink into another actor's private work tree."""
    try:
        return path.is_file() and not path.is_symlink()
    except OSError:
        return False



def trusted_system_binary_present(name: str, path: Path) -> bool:
    """Recognize the common same-directory versioned /usr/bin/python3 symlink.

    This only reports metadata. It never executes the target, follows a
    chain of links, or accepts an arbitrary link out of /usr/bin.
    """
    try:
        if name == "python3" and path == BINS["python3"] and path.is_symlink():
            link = os.readlink(path)
            if not re.fullmatch(r"python3\.[0-9]{1,2}", link):
                return False
            target = path.parent / link
            return regular_file_present(target) and os.access(target, os.X_OK)
        return regular_file_present(path) and os.access(path, os.X_OK)
    except (OSError, ValueError):
        return False


def directory_present(path: Path) -> bool:
    try:
        return path.is_dir() and not path.is_symlink()
    except OSError:
        return False


def safe_disk_gib(path: Path) -> float | None:
    """Report only aggregate available capacity of the *existing* runtime mount."""
    try:
        if not directory_present(path):
            return None
        stat = os.statvfs(path)
        return round((stat.f_bavail * stat.f_frsize) / (1024 ** 3), 2)
    except (OSError, ValueError):
        return None


def snapshot() -> dict:
    if pwd.getpwuid(os.geteuid()).pw_name != "githubops":
        raise PermissionError("EXISTING_GITHUBOPS_OWNER_REQUIRED")

    limits = {k: read_scalar(v) for k, v in KERNEL.items()}
    cgroup = {k: read_scalar(v) for k, v in CGROUP.items()}
    tools = {k: trusted_system_binary_present(k, v) for k, v in BINS.items()}
    sources = {
        k: (directory_present(v) if k == "factory_runtime_root"
            else regular_file_present(v))
        for k, v in SOURCE.items()
    }
    available = limits.get("max_user_namespaces")
    # A nonzero namespace limit alone proves neither unprivileged permission
    # nor a networkless/host-hidden sandbox; do not overclaim.
    namespace_capacity_indicated = (
        available is not None and available.isdigit() and int(available) > 0
    )
    return {
        "schema": SCHEMA,
        "host_role": "vps",
        "expected_user_verified": True,
        "read_only": True,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "security_prerequisites": {
            "binaries_present": tools,
            "kernel_limits_observed": limits,
            "cgroup_limits_observed": cgroup,
            "namespace_capacity_indicated_not_proven": namespace_capacity_indicated,
            "rootless_networkless_sandbox_attested": False,
            "host_secrets_hidden_attested": False,
        },
        "source_presence_not_running_workers": sources,
        "factory_runtime_disk_free_gib": safe_disk_gib(RUNTIME),
        "unknowns": {
            "cgroup_is_canonical_worker_quota": True,
            "networkless_execution_verified": True,
            "canonical_active_worker_verified": True,
            "model_inference_provider_verified": True,
        },
        "attestation": {
            "changes_made": False,
            "factory_started_or_stopped": False,
            "namespace_created": False,
            "agent_rows_modified": False,
            "payment_or_network_request_made": False,
        },
    }


if __name__ == "__main__":
    try:
        report = snapshot()
        print("MOJTABA_VPS_SANDBOX_CAPABILITY_READONLY=" +
              json.dumps(report, ensure_ascii=True, separators=(",", ":"), sort_keys=True))
    except (PermissionError, OSError) as exc:
        # Never leak paths, usernames, process details or exceptions.
        raise SystemExit("MOJTABA_VPS_SANDBOX_CENSUS_BLOCKED") from None
