#!/usr/bin/env python3
"""Prepare and verify a source-only, nonproduction Zomorod ERP transfer bundle.

This is an engineering handoff bundle, NOT a release, migration, site deployment
or proof that a company can operate the software in production.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import time

FILES = (
    "content/zomorod-business/.htaccess",
    "content/zomorod-business/index.php",
    "content/zomorod-business/app.php",
    "content/zomorod-business/insights.php",
    "content/zomorod-business/command_center.php",
    "content/zomorod-business/command_quality.php",
    "content/zomorod-business/command_planner.php",
    "content/zomorod-business/workflow_desk.php",
    "scripts/zomorod_company_private_bridge_v4.py",
    "scripts/zomorod_bridge_v5_private_e2e.py",
    "scripts/test_zomorod_company_private_bridge_v4.py",
    "scripts/zomorod_command_center_synthetic_qa.php",
    "scripts/zomorod_command_quality_synthetic_qa.php",
    "scripts/zomorod_command_planner_synthetic_qa.php",
    "scripts/zomorod_workflow_desk_synthetic_qa.php",
)
STATUS = {
    "source_bundle": "prepared",
    "base_accounting": "implemented_not_production_certified",
    "executive_reporting": "implemented_not_production_certified",
    "company_command_center": "implemented_not_production_certified",
    "approval_workflows": "implemented_test_pending_onsite",
    "private_command_receiver": "implemented_no_chat_signer",
    "automation_scheduling": "not_enabled_by_owner_instruction",
    "comprehensive_tax_payroll_treasury": "not_implemented",
    "agriculture_genetics_lims_mes": "not_implemented",
    "enterprise_iam_and_disaster_recovery": "unverified",
    "fully_autonomous_master_agent": "not_implemented",
    "live_owner_acceptance": "unverified",
}
BLOCKERS = (
    "Reconcile private live app.php and server-only extensions against source branch",
    "Perform authenticated owner acceptance test and role-permission tests",
    "Verify signed ChatGPT command transport without revealing signing credentials",
    "Install and test isolated live workflow module with backups and rollback",
    "Finish statutory accounting, payroll, tax, HR, procurement, agriculture, "
    "laboratory, manufacturing and contracts modules",
    "Prove real backup restore and recovery time / point objectives",
    "Pass independent security, financial accuracy and audit trail reviews",
    "Do not create recurring automation until owner explicitly reauthorizes",
)


def file_bytes(root: Path, name: str) -> bytes:
    p = root / name
    if p.is_symlink() or not p.is_file():
        raise ValueError("Unexpected missing file or symlink: " + name)
    data = p.read_bytes()
    if not data or len(data) > 2_000_000:
        raise ValueError("Invalid code file size: " + name)
    return data


def ti(name: str, data: bytes) -> tarfile.TarInfo:
    entry = tarfile.TarInfo("zomorod-erp-dev/" + name)
    entry.size = len(data)
    entry.mode = 0o644
    entry.uid = entry.gid = 0
    entry.mtime = 0
    return entry


def write_bundle(root: Path, target: Path) -> dict:
    root = root.resolve()
    entries = []
    payload = {}
    for name in FILES:
        b = file_bytes(root, name)
        payload[name] = b
        entries.append({"path": name, "bytes": len(b),
                        "sha256": hashlib.sha256(b).hexdigest()})
    manifest = {
        "format": "zomorod-erp-development-handoff-v1",
        "deployable": False,
        "reproducible_files": True,
        "file_count": len(entries),
        "included": entries,
        "capabilities": STATUS,
        "blocking_gates": list(BLOCKERS),
        "secret_material_included": False,
        "production_data_included": False,
        "caveat": "Offline development bundle only; never run as production installation automatically.",
    }
    manifest_b = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
                  + "\n").encode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(target, "w:gz", format=tarfile.PAX_FORMAT) as tar:
        for name, data in payload.items():
            tar.addfile(ti(name, data), io.BytesIO(data))
        tar.addfile(ti("MANIFEST.json", manifest_b), io.BytesIO(manifest_b))
    verify_bundle(target)
    return manifest


def verify_bundle(path: Path) -> None:
    with tarfile.open(path, "r:gz") as tar:
        members = tar.getmembers()
        actual_names = [m.name for m in members]
        wanted = ["zomorod-erp-dev/" + f for f in FILES]
        wanted.append("zomorod-erp-dev/MANIFEST.json")
        if set(actual_names) != set(wanted) or len(actual_names) != len(wanted):
            raise ValueError("Unexpected archive contents")
        if any(not m.isfile() or m.issym() or m.islnk() or
               m.name.startswith("/") or ".." in Path(m.name).parts for m in members):
            raise ValueError("Unsafe archive path or type")
        mbytes = tar.extractfile("zomorod-erp-dev/MANIFEST.json").read()
        manifest = json.loads(mbytes)
        if manifest.get("deployable") is not False:
            raise ValueError("Unsafe release readiness status")
        expected = {item["path"]: item for item in manifest["included"]}
        for name in FILES:
            buf = tar.extractfile("zomorod-erp-dev/" + name).read()
            if len(buf) != expected[name]["bytes"] or (
                hashlib.sha256(buf).hexdigest() != expected[name]["sha256"]
            ):
                raise ValueError("Handoff source checksum mismatch: " + name)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--output", type=Path, default=Path("dist/zomorod-erp-development-handoff.tar.gz"))
    ap.add_argument("--verify", type=Path)
    opts = ap.parse_args()
    if opts.verify:
        verify_bundle(opts.verify)
        print("TRANSFER_PACKAGE_INTEGRITY=PASS")
    else:
        manifest = write_bundle(opts.root, opts.output)
        print("TRANSFER_PACKAGE_CREATED=YES")
        print("FILE_COUNT=" + str(manifest["file_count"]))
        print("SOURCE_SHA256_MANIFEST=YES")
        print("PRODUCTION_DEPLOYABLE=NO")
        print("GATE_BLOCKERS=" + str(len(manifest["blocking_gates"])))
