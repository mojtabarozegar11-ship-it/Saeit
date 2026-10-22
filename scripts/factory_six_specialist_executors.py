#!/usr/bin/env python3
"""Six real *private* specialist worker executions, never fake native QA50/1000.

The six unproven families are F12 F13 F14 F16 F17 F26. Five use
the existing executable seven-gap manufacturers; F14 uses the proven
browser-game renderer. Every acceptance independently reopens the actual
produced ZIP, hashes each member, and checks safety fields. A source demo
is not an Android APK, Windows EXE, ONNX model, or independent game review.
"""
import argparse
import fcntl
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

SCHEMA = "saeit.factory.six-specialist-executors.v1"
FAMILIES = ("F12", "F13", "F14", "F16", "F17", "F26")
NAMES = {"F12": "mobile_puzzle_game", "F13": "desktop_puzzle_game",
         "F16": "mobile_inventory_app", "F17": "desktop_inventory_software",
         "F26": "machine_learning_model"}
REQUIRED = {
    "F12": {"index.html", "game.js", "levels.json", "README.txt"},
    "F13": {"game.py", "levels.json", "README.txt"},
    "F16": {"index.html", "app.js", "examples.json", "README.txt"},
    "F17": {"desktop.py", "sample.csv", "cases.json", "README.txt"},
    "F26": {"models.json", "predict.py", "README.txt"},
}
BLOCKERS = {
    "F12": ("real_signed_apk_or_aab", "physical_android_device_tests"),
    "F13": ("signed_windows_exe_or_appimage", "desktop_gui_install_test"),
    "F14": ("actual_browser_gameplay", "independent_player_and_novelty_review"),
    "F16": ("real_signed_apk_or_aab", "android_storage_and_accessibility_tests"),
    "F17": ("native_exe_or_appimage_install_test", "independent_security_scan"),
    "F26": ("onnx_or_pth_runtime_export", "real_world_data_bias_and_validation"),
}
HEX = re.compile(r"^[0-9a-f]{64}$")

def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(65536), b""):
            h.update(block)
    return h.hexdigest()

def load(filename, name):
    path = Path(__file__).resolve().parent / filename
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("SIX_PINNED_SPECIALIST_MISSING:" + filename)
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def read(path):
    p = Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size > 2_000_000:
        raise RuntimeError("SIX_RECEIPT_UNSAFE")
    value = json.loads(p.read_text(encoding="utf8"))
    if not isinstance(value, dict):
        raise RuntimeError("SIX_RECEIPT_NOT_OBJECT")
    return value

def atomic(path, data):
    if path.is_symlink() or path.parent.is_symlink():
        raise RuntimeError("SIX_UNSAFE_STATE")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    raw = (json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".six-")
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def inspect_zip(archive, prefix, expected):
    if archive.is_symlink() or not archive.is_file() or not 0 < archive.stat().st_size < 20_000_000:
        raise RuntimeError("SIX_ARCHIVE_UNSAFE")
    with zipfile.ZipFile(str(archive)) as z:
        entries = z.infolist()
        names = [i.filename for i in entries]
        if (not names or len(names) != len(set(names)) or len(names) > 80
                or z.testzip() is not None
                or set(names) != {(prefix + "/" if prefix else "") + n for n in expected}
                or any(i.is_dir() or i.flag_bits & 1 or i.file_size > 4_000_000
                       or ((i.external_attr >> 16) & 0o170000) == 0o120000
                       for i in entries)):
            raise RuntimeError("SIX_ARCHIVE_INTEGRITY_FAILED")
        return {n: hashlib.sha256(z.read((prefix + "/" if prefix else "") + n)).hexdigest() for n in expected}

def verify_five(root, family, reply):
    if family not in NAMES or reply.get("family_id") != family:
        raise RuntimeError("SIX_BUILDER_IDENTITY_MISMATCH")
    name = "fieldwork_" + NAMES[family] + "_pilot"
    digest = reply.get("private_archive_sha256")
    if not isinstance(digest, str) or not HEX.fullmatch(digest):
        raise RuntimeError("SIX_BUILDER_HASH_MISSING")
    version = root / "engineering-gaps" / "seven-builders" / name / digest[:20]
    if version.is_symlink() or not version.is_dir():
        raise RuntimeError("SIX_BUILDER_VERSION_MISSING")
    receipt = read(version / "technical_receipt.json")
    if (receipt.get("schema") != "zomorodmelal.factory.seven-gap-private.v1"
            or receipt.get("family_id") != family
            or receipt.get("private_archive_sha256") != digest
            or receipt.get("commercial_release_allowed") is not False
            or receipt.get("independent_quality_1000_passed") is not False
            or receipt.get("public_listing_enabled") is not False
            or receipt.get("native_distribution_verified") is not False):
        raise RuntimeError("SIX_BUILDER_RECEIPT_CONTRACT_INVALID")
    archive = version / (name + "-internal-qa.zip")
    if sha(archive) != digest:
        raise RuntimeError("SIX_BUILDER_ZIP_HASH_MISMATCH")
    source_files = receipt.get("source_files")
    if not isinstance(source_files, dict) or not REQUIRED[family].issubset(source_files):
        raise RuntimeError("SIX_REQUIRED_PRODUCT_FILES_MISSING")
    hashes = inspect_zip(archive, name, set(source_files))
    if any(not isinstance(h, str) or not HEX.fullmatch(h) or hashes[n] != h
           for n, h in source_files.items()):
        raise RuntimeError("SIX_PRODUCT_BYTES_DONT_MATCH_RECEIPT")
    source = version / name
    if source.is_symlink() or not source.is_dir():
        raise RuntimeError("SIX_PRODUCT_SOURCE_MISSING")
    if any(not (source / n).is_file() or (source / n).is_symlink()
           or sha(source / n) != h for n, h in hashes.items()):
        raise RuntimeError("SIX_PRODUCT_SOURCE_HASH_MISMATCH")
    if family == "F26":
        models = json.loads((source / "models.json").read_text(encoding="utf8"))
        if len(models) != 48 or len({x["id"] for x in models}) != 48:
            raise RuntimeError("SIX_ML_TRAINING_BATCH_UNVERIFIED")
    return {"family": family, "agent_executed": True,
            "technical_candidate_hash_verified": True,
            "format": "source_pilot_not_native_binary",
            "archive_sha256": digest, "source_count": len(hashes),
            "actual_checks": receipt.get("actual_checks", []),
            "blockers": list(BLOCKERS[family]),
            "native_target_verified": False,
            "quality_1000_certified": False, "commercial_release": False}

class GameHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.js = False
        self.controls = False
    def handle_starttag(self, tag, attrs):
        v = dict(attrs)
        if tag == "script" and v.get("src") == "game.js":
            self.js = True
        if tag in ("button", "canvas") or v.get("id") in ("board", "game"):
            self.controls = True

def verify_browser(folder):
    html = (folder / "mini_game.html").read_text(encoding="utf8")
    script = (folder / "game.js").read_text(encoding="utf8")
    parser = GameHTML()
    parser.feed(html)
    if not parser.js or not parser.controls or len(script) < 100:
        raise RuntimeError("SIX_BROWSER_GAME_NOT_INTERACTIVE")
    node = shutil.which("node")
    if node:
        result = subprocess.run([node, "--check", str(folder / "game.js")],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=20, check=False)
        if result.returncode:
            raise RuntimeError("SIX_BROWSER_JAVASCRIPT_PARSE_FAILED")
    return bool(node)

def build_browser(root):
    formats = load("factory_specialist_formats.py", "six_pinned_browser_renderer")
    base = root / "engineering-gaps" / "six-missing-executors" / "F14"
    if base.is_symlink() or base.parent.is_symlink():
        raise RuntimeError("SIX_BROWSER_UNSAFE_ROOT")
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".f14-", dir=str(base)))
    try:
        formats.render("F14", stage)
        # Repackage exact original renderer outputs deterministically: zipfile.write
        # otherwise embeds new filesystem timestamps and fakes a new version.
        bundle = stage / "browser_game.zip"
        with zipfile.ZipFile(str(bundle), "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for member in ("game.js", "mini_game.html"):
                info = zipfile.ZipInfo(member, date_time=(2020, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, (stage / member).read_bytes())
        names = {"mini_game.html", "game.js", "browser_game.zip"}
        if not all((stage / n).is_file() and not (stage / n).is_symlink() for n in names):
            raise RuntimeError("SIX_BROWSER_DELIVERABLES_MISSING")
        syntax_checked = verify_browser(stage)
        nested = inspect_zip(stage / "browser_game.zip", "", {"mini_game.html", "game.js"})
        if any(nested[n] != sha(stage / n) for n in ("mini_game.html", "game.js")):
            raise RuntimeError("SIX_BROWSER_BUNDLE_MISMATCH")
        hashes = {n: sha(stage / n) for n in sorted(names)}
        key = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
        receipt = {"schema": SCHEMA + ".f14-private-pilot",
                   "family": "F14", "artifact_sha256": hashes["browser_game.zip"],
                   "source_files": hashes, "node_syntax_checked": syntax_checked,
                   "browser_gameplay_real_device_tested": False,
                   "native_target_verified": False,
                   "quality_1000_certified": False, "commercial_release": False}
        atomic(stage / "technical_receipt.json", receipt)
        dest = base / key[:20]
        if dest.is_symlink():
            raise RuntimeError("SIX_BROWSER_VERSION_SYMLINK")
        if dest.exists():
            old = read(dest / "technical_receipt.json")
            if old != receipt or any(sha(dest / n) != hashes[n] for n in names):
                raise RuntimeError("SIX_BROWSER_EXISTING_ARTIFACT_TAMPERED")
        else:
            os.replace(str(stage), str(dest))
        return {"family": "F14", "agent_executed": True,
                "technical_candidate_hash_verified": True,
                "format": "html_js_zip_browser_pilot",
                "archive_sha256": hashes["browser_game.zip"],
                "source_count": len(hashes),
                "actual_checks": ["real_render", "html_controls", "zip_crc_sha256"]
                     + (["node_syntax_check"] if syntax_checked else []),
                "blockers": list(BLOCKERS["F14"]),
                "native_target_verified": False,
                "quality_1000_certified": False, "commercial_release": False}
    finally:
        if stage.exists():
            shutil.rmtree(str(stage))

def execute(root, family):
    if family == "F14":
        return build_browser(root)
    builder = load("factory_seven_missing_builders.py", "six_existing_real_builder")
    result = builder.create(root, family)
    return verify_five(root, family, result)

def run(root, all_six=False):
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise RuntimeError("SIX_PRIVATE_FACTORY_ROOT_REQUIRED")
    ops = root / "quality-excellence" / "six-agent-supervisor"
    if ops.is_symlink():
        raise RuntimeError("SIX_AGENT_SUPERVISOR_SYMLINK")
    ops.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock = ops / ".six-workers.lock"
    if lock.is_symlink():
        raise RuntimeError("SIX_WORKER_LOCK_UNSAFE")
    with lock.open("a+b") as fh:
        os.fchmod(fh.fileno(), 0o600)
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        cursor = ops / "state.json"
        previous = read(cursor) if cursor.exists() else {}
        if previous and previous.get("schema") != SCHEMA:
            raise RuntimeError("SIX_WORKER_STATE_SCHEMA_MISMATCH")
        turn = previous.get("turn", 0)
        if type(turn) is not int or turn < 0:
            raise RuntimeError("SIX_WORKER_STATE_TAMPERED")
        chosen = FAMILIES if all_six else (FAMILIES[turn % len(FAMILIES)],)
        outcomes = []
        for family in chosen:
            try:
                outcomes.append(execute(root, family))
            except (OSError, RuntimeError, ValueError, KeyError, TypeError,
                    subprocess.SubprocessError, zipfile.BadZipFile) as err:
                outcomes.append({"family": family, "agent_executed": False,
                                 "technical_candidate_hash_verified": False,
                                 "failure_class": type(err).__name__,
                                 "blockers": list(BLOCKERS[family]),
                                 "native_target_verified": False,
                                 "quality_1000_certified": False,
                                 "commercial_release": False})
        summary = {"schema": SCHEMA, "requested_master": "moj_1ro_1",
                   "master_identity_verified": False,
                   "runtime_dispatcher": "factory_40_execution_controller",
                   "registered_workers": list(FAMILIES),
                   "selected": list(chosen), "outcomes": outcomes,
                   "technical_candidates_rechecked": sum(
                       bool(o["technical_candidate_hash_verified"]) for o in outcomes),
                   "native_50_stage_executors_certified": 0,
                   "independent_quality_1000_certified": 0,
                   "public_release_authorized": False, "sites_modified": 0,
                   "turn": turn + len(chosen)}
        atomic(cursor, {"schema": SCHEMA, "turn": summary["turn"]})
        atomic(ops / "last-execution.json", summary)
        if all_six:
            # A concurrent cron --tick must NEVER erase evidence of the
            # six-family activation batch. Keep a separately addressable
            # complete result plus an immutable hash-named private receipt.
            raw = json.dumps(summary, sort_keys=True, separators=(",", ":")).encode() + bytes([10])
            proof_dir = ops / "complete-six-proofs"
            if proof_dir.is_symlink():
                raise RuntimeError("SIX_COMPLETE_PROOF_ROOT_UNSAFE")
            proof_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            proof = proof_dir / (hashlib.sha256(raw).hexdigest() + ".json")
            if proof.is_symlink():
                raise RuntimeError("SIX_COMPLETE_PROOF_SYMLINK")
            if proof.exists():
                if proof.read_bytes() != raw:
                    raise RuntimeError("SIX_COMPLETE_PROOF_CONFLICT")
            else:
                with proof.open("xb") as out:
                    out.write(raw)
                    out.flush()
                    os.fsync(out.fileno())
                os.chmod(proof, 0o600)
            atomic(ops / "last-full-six-execution.json", summary)
        print("FACTORY_SIX_AGENT_EXECUTION=" + json.dumps(summary, sort_keys=True))
        return summary

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--factory-private", required=True)
    p.add_argument("--all", action="store_true")
    a = p.parse_args()
    result = run(a.factory_private, all_six=a.all)
    return 0 if all(o["technical_candidate_hash_verified"] for o in result["outcomes"]) else 2

if __name__ == "__main__":
    sys.exit(main())
