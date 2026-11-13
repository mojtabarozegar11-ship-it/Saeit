#!/usr/bin/env python3
"""Stream a hash-pinned Zomorod candidate to the cPanel verifier: no host writes."""
from __future__ import annotations

import base64
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys
import zipfile

REPO = Path(__file__).resolve().parents[1]
GUARD = REPO / "scripts/zomorod_fields_guard_20261113.py"
PINNED_GUARD_BLOB = "aeffb90f93e690bcc94d320dcee5d9ed9b4c2e32"
BASELINE_COMMIT = "1a9e83144d1d30228ee62bf793e0e13f23894eb1"
PYTHON_CHOICES = (
    "python3.13", "python3.12", "python3.11", "python3.10",
    "python3.9", "python3.8", "python3",
    "/opt/alt/python313/bin/python3.13",
    "/opt/alt/python312/bin/python3.12",
    "/opt/alt/python311/bin/python3.11",
    "/opt/alt/python310/bin/python3.10",
    "/opt/alt/python39/bin/python3.9",
    "/opt/alt/python38/bin/python3.8",
    "/home/zomorod2/virtualenv/Saeit/3.11/bin/python",
    "/home/zomorod2/virtualenv/Saeit/3.10/bin/python",
)

def build_candidate(mod):
    prior = {
        name: subprocess.check_output(
            ["git", "show", BASELINE_COMMIT + ":content/zomorod-vision-v3/" + name],
            cwd=REPO, timeout=20)
        for name in mod.FILES
    }
    candidate = {
        name: (REPO / "content/zomorod-vision-v3" / name).read_bytes()
        for name in mod.FILES + mod.CREATED
    }
    mod.validate_candidate_maps(prior, candidate)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6) as archive:
        for prefix, files in (("old", prior), ("new", candidate)):
            for name, value in sorted(files.items()):
                info = zipfile.ZipInfo(prefix + "/" + name)
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o600) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, value)
    return output.getvalue()

def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: sender VERIFIED_SSH_CONFIG")
    config = Path(sys.argv[1])
    if not config.is_file() or config.is_symlink():
        raise SystemExit("Verified SSH configuration is missing")
    code = GUARD.read_bytes()
    spec = importlib.util.spec_from_file_location("zomorod_stream_guard", GUARD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if mod.git_blob(code) != PINNED_GUARD_BLOB:
        raise SystemExit("Pinned source changed: refuse remote verification")
    bundle = build_candidate(mod)
    if len(bundle) > 16 * 1024 * 1024:
        raise SystemExit("Bundle too large: refuse remote verification")
    encoded = base64.b64encode(code).decode("ascii")
    bootstrap = (
        'import base64; ns={"__name__":"remote_stream_guard"}; '
        'exec(compile(base64.b64decode("' + encoded + '"), '
        '"pinned_guard.py", "exec"), ns); '
        'ns["inspect_streamed_candidate"]()'
    )
    remote = (
        'for py in ' + ' '.join(shlex.quote(py) for py in PYTHON_CHOICES) +
        '; do if command -v "$py" >/dev/null 2>&1 && '
        '"$py" -c "import sys;sys.exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; '
        'then exec "$py" -B -c ' + shlex.quote(bootstrap) +
        '; fi; done; echo CPANEL_COMPATIBLE_PYTHON_NOT_FOUND >&2; exit 70'
    )
    proc = subprocess.run(
        ["ssh", "-T", "-F", str(config), "saeit-cpanel", remote],
        input=bundle, capture_output=True, timeout=130, check=False)
    if proc.returncode:
        sys.stderr.write("ZOMOROD_PRIVATE_STREAM_AUDIT_FAILED\n")
        sys.stderr.write(proc.stderr.decode("utf-8", "replace")[-2500:])
        raise SystemExit(proc.returncode)
    response = json.loads(proc.stdout.decode("utf-8").strip())
    if (response.get("status") != "READ_ONLY_STAGE_STREAM_VERIFIED" or
            response.get("prior_source_files_verified") != 3 or
            response.get("candidate_files_verified") != 15 or
            response.get("stage_hashes_verified") is not True or
            response.get("host_files_written") != 0 or
            response.get("deployment_authorized") is not False or
            response.get("deployment_performed") is not False):
        raise SystemExit("Host stream audit did not produce required read-only proof")
    print(json.dumps(response, sort_keys=True))
    print("ZOMOROD_HOST_CANDIDATE_IN_MEMORY_VERIFIED=YES")

if __name__ == "__main__":
    main()
