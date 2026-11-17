#!/usr/bin/env python3
"""Deterministic, source-only MOJ-PROP-01 release closure. NO installer.

Packages the first-party Plan1 app and reviewed Django integration sources
exclusively in ephemeral GitHub Actions runner temp. NEVER connects to
production, modifies cPanel, reads databases, contacts customers, sends TRX,
or authorizes deploy. A tar is NOT a deployable or legally approved product.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tarfile

ROOT = Path(__file__).resolve().parents[1]
APP = "prop_firm"
EXPECTED_MIGRATIONS = (
    "0001_initial.py",
    "0002_provisional_profit_ledger.py",
    "0003_social_evidence.py",
    "0004_four_week_challenge.py",
    "0005_trade_origin_and_position_id.py",
    "0006_ten_plan_enrollment.py",
    "0007_equity_broker_source.py",
    "0008_prospect_contact_intake.py",
)
REQUIRED = (
    "config/urls.py",
    "config/settings.py",
    "core/moj_prop_views.py",
    "core/templates/mojplaywin/moj_prop.html",
    "core/templates/mojplaywin/moj_prop_dashboard.html",
    "core/templates/mojplaywin/moj_prop_interest_form_d.html",
    "prop_firm/apps.py",
    "prop_firm/__init__.py",
    "prop_firm/models.py",
    "prop_firm/lead_models.py",
    "prop_firm/moj_prop_page.py",
    "prop_firm/portal.py",
    "prop_firm/migrations/__init__.py",
) + tuple("prop_firm/migrations/" + m for m in EXPECTED_MIGRATIONS)
MAX_BYTES = 384 * 1024
MAX_FILES = 128
BUNDLE_NAME = "mojprop-plan1-source-closure-c147.tar"
MANIFEST_NAME = "mojprop-plan1-source-closure-c147.json"
REFERENCE_ONLY = {"config/settings.py", "config/urls.py"}


def _file_bytes(root: Path, name: str) -> bytes:
    if not (isinstance(name, str) and name and
            not name.startswith("/") and
            all(part not in ("", ".", "..") for part in name.split("/"))):
        raise ValueError("unsafe relative source path")
    target = root / name
    if target.is_symlink() or root not in target.parents:
        raise ValueError("symbolic or escaped source not permitted")
    meta = target.lstat()
    if not stat.S_ISREG(meta.st_mode) or not 0 < meta.st_size <= MAX_BYTES:
        raise ValueError("missing, empty, or unreviewably large source")
    # Symlinked parent directories are forbidden in the bundle.
    current = target.parent
    while current != root:
        if current.is_symlink() or not current.is_dir():
            raise ValueError("unsafe source parent")
        current = current.parent
    return target.read_bytes()


def _path_view_mappings(blob: bytes) -> set[tuple[str, str]]:
    tree = ast.parse(blob.decode("utf-8"), mode="exec")
    result = set()
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "path" and len(n.args) >= 2):
            continue
        if (isinstance(n.args[0], ast.Constant) and
                isinstance(n.args[0].value, str) and
                isinstance(n.args[1], ast.Name)):
            result.add((n.args[0].value, n.args[1].id))
    return result


def _installed_app(blob: bytes) -> bool:
    tree = ast.parse(blob.decode("utf-8"), mode="exec")
    for node in tree.body:
        if not (isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "INSTALLED_APPS"
                        for t in node.targets)):
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple)):
            continue
        return any(isinstance(t, ast.Constant)
                   and t.value == "prop_firm.apps.MojPropConfig"
                   for t in node.value.elts)
    return False


def collect(root: Path = ROOT) -> dict[str, bytes]:
    root = Path(root).resolve(strict=True)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("source root must be a normal directory")
    files = set(REQUIRED)
    for mask in ("prop_firm/*.py", "prop_firm/*.json",
                 "prop_firm/migrations/*.py"):
        for path in root.glob(mask):
            files.add(path.relative_to(root).as_posix())
    if len(files) > MAX_FILES:
        raise ValueError("unbounded source inventory")
    content = {name: _file_bytes(root, name) for name in sorted(files)}
    for name, body in content.items():
        if name.endswith(".py"):
            ast.parse(body.decode("utf-8"), filename=name)
    routes = _path_view_mappings(content["config/urls.py"])
    if not {
        ("moj-prop-interest/form/", "moj_prop_interest_form"),
        ("moj-prop-interest/", "moj_prop_interest"),
    } <= routes:
        raise ValueError("Plan1 first-party route pair incomplete")
    if not _installed_app(content["config/settings.py"]):
        raise ValueError("prop_firm not in INSTALLED_APPS")
    view = content["core/moj_prop_views.py"].decode("utf-8")
    if ("def moj_prop_interest_form(request):" not in view
            or "def moj_prop_interest(request):" not in view
            or "@csrf_protect" not in view
            or "contact_consent" not in view):
        raise ValueError("CSRF/consent view contract missing")
    form = content["core/templates/mojplaywin/moj_prop_interest_form_d.html"]
    for required in (b'action="/moj-prop-interest/"', b"{% csrf_token %}",
                     b'name="plan_code" value="MOJ-PROP-01"',
                     b'name="contact_consent"', b'method="post"'):
        if required not in form:
            raise ValueError("genuine Plan1 form contract missing")
    for denied in (b"walletconnect", b"sendtransaction",
                   b'name="private_key"'):
        if denied in form.lower():
            raise ValueError("checkout/private-key code in opt-in form")
    migration = content["prop_firm/migrations/0008_prospect_contact_intake.py"]
    if (b'"0007_equity_broker_source"' not in migration and
            b"'0007_equity_broker_source'" not in migration):
        raise ValueError("Plan1 prospect schema migration chain missing")
    return content


def manifest(files: dict[str, bytes]) -> dict:
    if not files or len(files) > MAX_FILES:
        raise ValueError("invalid bundle file count")
    return {
        "schema": "mojprop.plan1.source_closure.c147.v1",
        "product": "MOJ-PROP-01",
        "type": "reviewed-source-only-not-an-installer",
        "file_count": len(files),
        "source_bytes": sum(map(len, files.values())),
        "files": [
            {"path": name, "size": len(data),
             "sha256": hashlib.sha256(data).hexdigest(),
             "installation_role": ("reference-only-do-not-overwrite-live"
                                   if name in REFERENCE_ONLY
                                   else "requires-review-and-gated-release")}
            for name, data in sorted(files.items())
        ],
        "db_app_media_restore_verified": False,
        "passenger_runtime_parity_verified": False,
        "merchant_authorized": False,
        "customer_consent_post_executed": False,
        "tron_invoice_created": False,
        "funded_broker_account_proven": False,
        "production_deploy_authorized": False,
    }


def tar_bytes(files: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as tar:
        for name, data in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(data))
    return stream.getvalue()


def package_to_runner(files: dict[str, bytes], target: Path) -> dict:
    """Write only two artifacts beneath RUNNER_TEMP; NEVER on VPS or cPanel."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise PermissionError("package operation only on ephemeral CI runner")
    temp_raw = os.environ.get("RUNNER_TEMP")
    if not temp_raw:
        raise PermissionError("RUNNER_TEMP absent")
    temp = Path(temp_raw).resolve(strict=True)
    if temp.is_symlink() or not temp.is_dir():
        raise PermissionError("unsafe runner temp")
    dest = Path(target)
    if (dest != temp / "mojprop-c147" or
            dest.exists() and dest.is_symlink()):
        raise PermissionError("must use exact isolated CI temp output directory")
    dest.mkdir(mode=0o700, exist_ok=True)
    if dest.is_symlink() or dest.resolve() != temp / "mojprop-c147":
        raise PermissionError("unsafe output directory")
    for name in (BUNDLE_NAME, MANIFEST_NAME):
        if (dest / name).exists() or (dest / name).is_symlink():
            raise PermissionError("refusing overwrite of existing artifact")
    archive = tar_bytes(files)
    index = manifest(files)
    (dest / BUNDLE_NAME).write_bytes(archive)
    (dest / MANIFEST_NAME).write_text(
        json.dumps(index, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8")
    return {
        "schema": index["schema"],
        "file_count": index["file_count"],
        "archive_sha256": hashlib.sha256(archive).hexdigest(),
        "source_bytes": index["source_bytes"],
        "ephemeral_only": True,
        "production_deploy_authorized": False,
        "db_app_media_restore_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=("audit", "package"), required=True)
    args = parser.parse_args()
    files = collect()
    data = manifest(files)
    if args.action == "audit":
        out = {"schema": data["schema"], "file_count": data["file_count"],
               "source_bytes": data["source_bytes"],
               "source_contract_verified": True,
               "db_app_media_restore_verified": False,
               "production_deploy_authorized": False}
    else:
        temp = Path(os.environ.get("RUNNER_TEMP", "/not-a-runner"))
        out = package_to_runner(files, temp / "mojprop-c147")
    print("MOJPROP_C147_REVIEWED_SOURCE_ONLY=" + json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
