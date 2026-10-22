#!/usr/bin/env python3
"""Independent machine-evidence reviewer for six private native factory lines.

Never mistakes a successful CI build for independent professional acceptance.
Reads original VPS bundles again, reconstructs hashes, identifies remediable
defects and creates a stable, private, immutable per-family work queue.
No site, warehouse, payment or public release paths are addressed.
Python 3.8+; no third-party runtime dependencies.
"""
import argparse
import hashlib
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile

FAMILIES = ("F12", "F13", "F14", "F16", "F17", "F26")
COUNT = {"F12": 2, "F13": 1, "F14": 2, "F16": 2, "F17": 1, "F26": 48}
ADAPTER = {
    "F12": "game_mobile_build", "F13": "game_desktop_build",
    "F14": "game_web_build", "F16": "app_mobile_build",
    "F17": "app_desktop_build", "F26": "ml_training"}
TARGET_GATES = {
    "F12": ["physical_android_touch_and_crash_test", "release_keystore_signature",
            "mobile_device_accessibility", "copyright_and_originality_review"],
    "F13": ["clean_install_playthrough_on_windows", "independent_security_scan",
            "rights_and_gameplay_novelty_review"],
    "F14": ["independent_blind_player_sessions", "physical_mobile_browser_test",
            "independent_original_gameplay_and_ip_review"],
    "F16": ["physical_android_storage_and_accessibility_test",
            "release_keystore_signature", "privacy_and_permissions_review"],
    "F17": ["independent_windows_clean_install_and_security_scan",
            "real_customer_workflow_coverage", "distribution_license_review"],
    "F26": ["representative_real_world_data", "independent_bias_and_leakage_audit",
            "external_holdout_reproducibility_and_model_card"]}
HEX = re.compile(r"^[0-9a-f]{64}$")
RUN = re.compile(r"^[0-9]{5,18}-[0-9]{1,3}$")
NAME = re.compile(r"^[A-Za-z0-9_.-]{3,96}$")
SCHEMA = "saeit.factory.six-native-independent-technical-review.v1"

def sha(blob):
    return hashlib.sha256(blob).hexdigest()

def strict_json(path, limit=150_000):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise RuntimeError("REVIEW_UNSAFE_OR_OVERSIZED_JSON")
    value = json.loads(path.read_text("utf8"))
    if not isinstance(value, dict):
        raise RuntimeError("REVIEW_EXPECTED_OBJECT")
    return value

def safe_members(archive, receipt):
    if archive.is_symlink() or not archive.is_file() or archive.stat().st_size > 220_000_000:
        raise RuntimeError("REVIEW_UNSAFE_ARCHIVE")
    expect = receipt.get("archive_members_sha256")
    if not isinstance(expect, dict) or not expect or len(expect)>60:
        raise RuntimeError("REVIEW_NO_MEMBERS")
    if any(not NAME.fullmatch(k) or not isinstance(v, str) or not HEX.fullmatch(v)
           for k,v in expect.items()):
        raise RuntimeError("REVIEW_INVALID_MEMBER_MANIFEST")
    if sha(archive.read_bytes()) != receipt.get("archive_sha256"):
        raise RuntimeError("REVIEW_ARCHIVE_HASH_CHANGED")
    with zipfile.ZipFile(archive) as z:
        members = z.infolist()
        if (len(members)!=len(expect) or set(z.namelist())!=set(expect)
                or sum(i.file_size for i in members)>300_000_000
                or z.testzip() is not None or any(i.flag_bits&1 or i.is_dir()
                or i.file_size>95_000_000 or ((i.external_attr>>16)&0o170000)==0o120000
                for i in members)):
            raise RuntimeError("REVIEW_ARCHIVE_MEMBER_STRUCTURE_INVALID")
        files={name:z.read(name) for name in expect}
    if any(sha(value)!=expect[name] for name,value in files.items()):
        raise RuntimeError("REVIEW_ARCHIVE_MEMBER_HASH_CHANGED")
    return files

class Accessibility(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canvas_has_accessible_name=False
        self.score_has_live_region=False
    def handle_starttag(self,tag,attrs):
        value=dict(attrs)
        if tag=="canvas" and value.get("id")=="board":
            self.canvas_has_accessible_name=bool(value.get("aria-label"))
        if value.get("id")=="score":
            self.score_has_live_region=value.get("role")=="status" or bool(value.get("aria-live"))

def review_family(directory, family, aggregate):
    if directory.is_symlink() or not directory.is_dir():
        raise RuntimeError("REVIEW_UNSAFE_FAMILY_FOLDER")
    receipt=strict_json(directory/"technical-native-receipt.json")
    if (receipt.get("schema")!="saeit.factory.private-six-native-candidate.v1"
          or receipt.get("family")!=family
          or receipt.get("format_candidate_count")!=COUNT[family]
          or receipt.get("actual_native_file_format_tested_in_ci") is not True
          or receipt.get("physical_device_matrix_verified") is not False
          or receipt.get("independent_specialist_review_verified") is not False
          or receipt.get("quality_1000_certified") is not False
          or receipt.get("commercial_release") is not False
          or receipt.get("public_transfer") is not False
          or receipt.get("owner_signature") is not None
          or receipt.get("archive_sha256")!=aggregate.get("archive_sha256")):
        raise RuntimeError("REVIEW_RECEIPT_PROVENANCE_POLICY_FAILED")
    files=safe_members(directory/"technical-native-candidate.zip",receipt)
    checked=[]
    deficiencies=[]
    if family in ("F12","F16"):
        for ext in (".apk",".aab"):
            candidates=[x for x in files if x.endswith(ext)]
            if len(candidates)!=1:
                raise RuntimeError("REVIEW_ANDROID_NATIVE_COUNT")
            with zipfile.ZipFile(io.BytesIO(files[candidates[0]])) as z:
                paths=set(z.namelist())
                prefix="base/" if ext==".aab" else ""
                manifest=(prefix+"manifest/AndroidManifest.xml" if ext==".aab"
                          else "AndroidManifest.xml")
                dex=prefix+"dex/classes.dex" if ext==".aab" else "classes.dex"
                if not {manifest,dex,prefix+"assets/index.html"}.issubset(paths):
                    raise RuntimeError("REVIEW_ANDROID_REQUIRED_BUILD_OUTPUT_MISSING")
        checked=["real_native_android_apk_aab_bytes","asset_and_dex_integrity",
                 "runner_debug_signature_assertion_in_source_receipt"]
    elif family in ("F13","F17"):
        exe=[blob for name,blob in files.items() if name.lower().endswith(".exe")]
        if len(exe)!=1 or len(exe[0])<30000 or exe[0][:2]!=b"MZ":
            raise RuntimeError("REVIEW_WINDOWS_EXE_NOT_NATIVE")
        offset=int.from_bytes(exe[0][0x3c:0x40],"little")
        if offset<64 or offset+4>len(exe[0]) or exe[0][offset:offset+4]!=b"PE\x00\x00":
            raise RuntimeError("REVIEW_WINDOWS_PE_SIGNATURE_MISSING")
        checked=["real_native_windows_pe_bytes","source_ci_executable_smoke_receipt"]
        if "windows-native-proof.json" in files:
            acceptance=json.loads(files["windows-native-proof.json"].decode("utf8"))
            detailed=acceptance.get("families",{}).get(family,{})
            if (acceptance.get("schema")!="saeit.factory.windows-native-interactive-acceptance.v1"
                    or acceptance.get("real_windows_runner_execute") is not True
                    or acceptance.get("independent_security_expert_approved") is not False
                    or acceptance.get("quality_1000_certified") is not False
                    or detailed.get("sha256")!=sha(exe[0])
                    or (family=="F13" and
                        (detailed.get("playthroughs_from_actual_exe")!=48
                         or detailed.get("level_paths_verified")!=48))
                    or (family=="F17" and
                        (detailed.get("real_packaged_csv_invoices_tested")!=6
                         or detailed.get("invalid_inventory_rows_rejected")!=9
                         or detailed.get("exact_decimal_math_verified") is not True))):
                raise RuntimeError("REVIEW_WINDOWS_INTERACTIVE_EVIDENCE_INCOMPLETE")
            checked.append("windows_real_pe_48_game_or_15_inventory_execution_proof")
    elif family=="F14":
        if not {"mini_game.html","game.js","browser-proof.json"}.issubset(files):
            raise RuntimeError("REVIEW_BROWSER_SOURCE_PROOF_MISSING")
        browser=json.loads(files["browser-proof.json"].decode("utf8"))
        if (browser.get("actual_chromium_executed") is not True
                or browser.get("real_interactive_movement_tested") is not True
                or browser.get("keyboard_and_restart_tested") is not True
                or set(browser.get("responsive_viewports_tested",[]))!={"mobile","desktop"}
                or browser.get("uncaught_js_errors")!=0
                or browser.get("external_network_requests")!=0
                or any(sha(files[name])!=browser["source_sha256"][name]
                       for name in ("mini_game.html","game.js"))):
            raise RuntimeError("REVIEW_BROWSER_PROOF_INCOMPLETE")
        parsed=Accessibility()
        parsed.feed(files["mini_game.html"].decode("utf8"))
        if not parsed.canvas_has_accessible_name:
            deficiencies.append("canvas_accessible_name_missing")
        if not parsed.score_has_live_region:
            deficiencies.append("score_live_region_missing")
        checked=["real_chromium_interactivity_receipt","original_html_js_sha_provenance",
                 "desktop_and_mobile_viewport_receipt","canvas_accessibility_static_check"]
    elif family=="F26":
        models=[name for name in files if name.endswith(".onnx")]
        if len(models)!=48 or not {"native-proof.json"}.issubset(files):
            raise RuntimeError("REVIEW_ONNX_MODEL_PROVENANCE_INCOMPLETE")
        proof=json.loads(files["native-proof.json"].decode("utf8"))
        if (proof.get("actual_onnxruntime_models_checked")!=48
                or proof.get("holdout_predictions_checked")!=192
                or proof.get("independent_quality_1000_certified") is not False
                or {row["file"]:row["sha256"] for row in proof["models"]}!=
                    {name:sha(files[name]) for name in models}):
            raise RuntimeError("REVIEW_ONNX_RUNTIME_RECEIPT_INVALID")
        checked=["48_real_onnx_byte_provenance","192_ci_synthetic_holdout_checks"]
    if not checked:
        raise RuntimeError("REVIEW_NO_INDEPENDENT_TECHNICAL_EVIDENCE")
    return {
        "family_id":family,"producer_adapter":ADAPTER[family],
        "target_controller":"factory_40_execution_controller",
        "requested_master":"moj_1ro_1","master_identity_verified":False,
        "artifact_sha256":receipt["archive_sha256"],
        "format_artifact_count":COUNT[family],
        "independent_machine_checks":checked,
        "remediable_source_defects":deficiencies,
        "unverified_specialist_or_physical_gates":TARGET_GATES[family],
        "status":("source_rework_required" if deficiencies
                  else "awaiting_independent_professional_validation"),
        "technical_native_artifact_integrity_verified":True,
        "independent_professional_approval":False,
        "quality_1000_certified":False,
        "commercial_release_authorized":False
    }

def immutable(path, value):
    if path.is_symlink() or path.parent.is_symlink():
        raise RuntimeError("REVIEW_UNSAFE_DESTINATION")
    raw=(json.dumps(value,sort_keys=True,indent=2)+"\n").encode("utf8")
    if path.exists():
        if path.read_bytes()!=raw:
            raise RuntimeError("REVIEW_IMMUTABLE_CONFLICT")
        return sha(raw)
    fd,tmp=tempfile.mkstemp(prefix=".review-",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,0o600)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return sha(raw)

def run(root, source_run, expected_aggregate_sha256=None):
    root=Path(root)
    if root.is_symlink() or not root.is_dir() or not RUN.fullmatch(source_run):
        raise RuntimeError("REVIEW_INVALID_PRIVATE_SOURCE")
    source=root/"native-candidate-evidence"/source_run
    if source.is_symlink() or not source.is_dir():
        raise RuntimeError("REVIEW_SOURCE_NOT_FOUND")
    anchor=source/"verified-six-private-native.json"
    if expected_aggregate_sha256 is not None:
        if not HEX.fullmatch(expected_aggregate_sha256) or sha(anchor.read_bytes())!=expected_aggregate_sha256:
            raise RuntimeError("REVIEW_EXPECTED_AGGREGATE_HASH_MISMATCH")
    summary=strict_json(anchor)
    if (summary.get("schema")!="saeit.factory.native-six-vps-aggregate.v1"
            or summary.get("six_families_verified")!=6
            or summary.get("candidate_native_file_count")!=56
            or summary.get("private_only") is not True
            or summary.get("production_release_authorized") is not False
            or summary.get("independent_specialist_quality_1000_certified")!=0
            or summary.get("sites_modified")!=0):
        raise RuntimeError("REVIEW_PREVIOUS_AGGREGATE_INVALID")
    rows=summary.get("files")
    if not isinstance(rows,list) or len(rows)!=6 or {
        x["family"] for x in rows}!=set(FAMILIES):
        raise RuntimeError("REVIEW_AGGREGATE_FAMILY_IDENTITY_INVALID")
    indexed={x["family"]:x for x in rows}
    reviewed=[]
    for family in FAMILIES:
        if indexed[family].get("native_candidate_files")!=COUNT[family] or (
                indexed[family].get("verified_on_vps") is not True):
            raise RuntimeError("REVIEW_AGGREGATE_NATIVE_COUNT_INVALID")
        reviewed.append(review_family(source/family,family,indexed[family]))
    report={
        "schema":SCHEMA,"source_run":source_run,
        "source_aggregate_sha256":sha(anchor.read_bytes()),
        "reviewed_families":6,"verified_native_candidate_files":56,
        "completed_professional_quality_1000_certifications":0,
        "independent_machine_review_performed":True,
        "master_controller_connected_to_this_queue":False,
        "commercial_release_authorized":False,"website_changes":0,
        "source_rework_needed":sum(bool(r["remediable_source_defects"]) for r in reviewed),
        "specialist_or_physical_review_needed":6,
        "families":reviewed,
    }
    directory=root/"quality-excellence"/"six-native-rework"/source_run
    if directory.is_symlink() or directory.parent.is_symlink():
        raise RuntimeError("REVIEW_QUEUE_SYMLINK")
    directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    for row in reviewed:
        immutable(directory/(row["family_id"]+".json"),row)
    report_sha=immutable(directory/"review.json",report)
    print("FACTORY_INDEPENDENT_NATIVE_REVIEW="+json.dumps({
        "families":6,"files":56,"source_rework_needed":report["source_rework_needed"],
        "external_specialist_gates":6,
        "quality1000_approved":0,"review_sha256":report_sha},sort_keys=True))
    return report

def latest_valid_source(root):
    base=Path(root)/"native-candidate-evidence"
    if base.is_symlink() or not base.is_dir():
        raise RuntimeError("REVIEW_LATEST_SOURCE_ROOT_MISSING")
    candidates=[]
    for entry in base.iterdir():
        if (not entry.is_symlink() and entry.is_dir()
                and RUN.fullmatch(entry.name)
                and (entry/"verified-six-private-native.json").is_file()
                and not (entry/"verified-six-private-native.json").is_symlink()):
            try:
                id_number,attempt=map(int,entry.name.split("-"))
            except (ValueError,TypeError):
                continue
            candidates.append((id_number,attempt,entry.name))
    if not candidates:
        raise RuntimeError("REVIEW_NO_COMPLETE_NATIVE_RUN")
    return max(candidates)[2]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--factory-private",required=True)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument("--source-run")
    group.add_argument("--latest",action="store_true")
    p.add_argument("--expected-aggregate-sha256")
    args=p.parse_args()
    source=(latest_valid_source(args.factory_private)
            if args.latest else args.source_run)
    run(args.factory_private,source,args.expected_aggregate_sha256)

if __name__=="__main__":
    main()
