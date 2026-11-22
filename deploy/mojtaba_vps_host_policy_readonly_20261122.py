"""Bounded, read-only VPS namespace/AppArmor/cgroup metadata receipt.

No execution/installation, no subprocess, no networking, no host secrets, no
worktree discovery, no writes, and no claim that sandbox isolation is proven.
Only the existing githubops localhost SSH forced command may use this source.
"""
from __future__ import annotations

import json
import os
import pwd
import re
import stat
from pathlib import Path

PREFIX = "MOJTABA_VPS_HOST_POLICY_READONLY="
CGROUP_ROOT = Path("/sys/fs/cgroup")
BWRAP = ("/usr/bin/bwrap", "/usr/local/bin/bwrap", "/bin/bwrap")
SYSCTLS = {
    "max_user_namespaces": Path("/proc/sys/user/max_user_namespaces"),
    "unprivileged_userns_clone": Path("/proc/sys/kernel/unprivileged_userns_clone"),
    "apparmor_restrict_unprivileged_userns":
        Path("/proc/sys/kernel/apparmor_restrict_unprivileged_userns"),
}
SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_.-]{1,160}$")
SAFE_RELEASE = re.compile(r"^[A-Za-z0-9_.+-]{1,30}$")


def bounded_read(path: Path, *, limit: int = 2048) -> str | None:
    """Read a fixed kernel metadata source, reject links and oversized bytes."""
    try:
        if path.is_symlink() or not path.is_file():
            return None
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
        if len(data) > limit or b"\x00" in data:
            return None
        return data.decode("ascii").strip()
    except (OSError, UnicodeError, ValueError):
        return None


def nonnegative(value: str | None) -> int | None:
    if value is None or not re.fullmatch(r"[0-9]{1,18}", value):
        return None
    try:
        return min(int(value), 10**15)
    except ValueError:
        return None


def mode_value(value: str | None) -> dict[str, str | int | None]:
    """Describe a kernel max or bounded numeric value without leaking paths."""
    if value == "max":
        return {"mode": "unlimited", "value": None}
    number = nonnegative(value)
    return {"mode": "limited" if number is not None else "unknown",
            "value": number}


def cpu_max(value: str | None) -> dict[str, str | int | None]:
    fields = value.split() if value is not None else []
    if len(fields) != 2:
        return {"mode": "unknown", "quota": None, "period": None}
    period = nonnegative(fields[1])
    if period is None or period <= 0:
        return {"mode": "unknown", "quota": None, "period": None}
    if fields[0] == "max":
        return {"mode": "unlimited", "quota": None, "period": period}
    quota = nonnegative(fields[0])
    if quota is None:
        return {"mode": "unknown", "quota": None, "period": None}
    return {"mode": "limited", "quota": quota, "period": period}


def cgroup_relative(value: str | None) -> tuple[str, ...] | None:
    """Accept only a single absolute cgroup-v2 path from proc metadata."""
    if value is None:
        return None
    paths = [line[3:] for line in value.splitlines()
             if line.startswith("0::")]
    if len(paths) != 1 or not paths[0].startswith("/"):
        return None
    if paths[0] == "/":
        return ()
    pieces = paths[0][1:].split("/")
    if not all(SAFE_SEGMENT.fullmatch(p) and p not in {".", ".."}
               for p in pieces):
        return None
    return tuple(pieces)


def cgroup_receipt() -> dict:
    rel = cgroup_relative(bounded_read(Path("/proc/self/cgroup"), limit=1024))
    cgroup_v2 = (CGROUP_ROOT / "cgroup.controllers").is_file()
    status = {"cgroup_v2_root_present": cgroup_v2,
              "current_v2_path_valid": rel is not None,
              "cpu_max": cpu_max(None),
              "memory_max": mode_value(None),
              "pids_max": mode_value(None),
              "memory_current_mib": None}
    if not cgroup_v2 or rel is None:
        return status
    directory = CGROUP_ROOT.joinpath(*rel)
    # Never resolve caller-controlled paths, and do not traverse symlinked
    # components even when a future kernel emits different cgroup metadata.
    cur = CGROUP_ROOT
    for part in rel:
        cur = cur / part
        if cur.is_symlink() or not cur.is_dir():
            return status
    status["cpu_max"] = cpu_max(bounded_read(directory / "cpu.max", limit=64))
    status["memory_max"] = mode_value(bounded_read(directory / "memory.max", limit=64))
    status["pids_max"] = mode_value(bounded_read(directory / "pids.max", limit=64))
    current = nonnegative(bounded_read(directory / "memory.current", limit=64))
    if current is not None:
        status["memory_current_mib"] = current // (1024 * 1024)
    return status


def release_info() -> dict[str, str | None]:
    # On many Linux distributions /etc/os-release is a legitimate symlink;
    # read only the fixed, package-owned fallback, never follow arbitrary links.
    data = (bounded_read(Path("/etc/os-release"), limit=4096)
            or bounded_read(Path("/usr/lib/os-release"), limit=4096)
            or "")
    result: dict[str, str | None] = {"id": None, "version_id": None}
    for line in data.splitlines():
        key, sep, value = line.partition("=")
        target = {"ID": "id", "VERSION_ID": "version_id"}.get(key)
        if sep and target:
            clean = value.strip().strip('"').strip("'")
            if SAFE_RELEASE.fullmatch(clean):
                result[target] = clean
    return result


def binary_present(path: str) -> bool:
    p = Path(path)
    try:
        info = p.lstat()
        return stat.S_ISREG(info.st_mode) and bool(info.st_mode & 0o111)
    except OSError:
        return False


def snapshot() -> dict:
    kernel = {name: nonnegative(bounded_read(path, limit=48))
              for name, path in SYSCTLS.items()}
    apparmor = bounded_read(Path("/proc/self/attr/current"), limit=256)
    return {
        "schema": "mojtaba.bot.ai.vps-host-policy.readonly.v1",
        "read_only": True,
        "os_release": release_info(),
        "kernel": kernel,
        "apparmor_profile_attached": (None if apparmor is None
                                     else apparmor != "unconfined"),
        "bwrap_trusted_paths": {p: binary_present(p) for p in BWRAP},
        "cgroup": cgroup_receipt(),
        "rootless_networkless_sandbox_attested": False,
        "host_secrets_hidden_attested": False,
        "worker_started_or_changed": False,
        "package_installed_or_config_changed": False,
    }


def main() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != "githubops":
        raise SystemExit("Wrong read-only host principal")
    print(PREFIX + json.dumps(snapshot(), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
