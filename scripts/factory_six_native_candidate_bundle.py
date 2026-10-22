#!/usr/bin/env python3
"""Deterministic private native candidate packaging; never commercial promotion.

Outputs two immutable-checkable files for private VPS transfer:
technical-native-candidate.zip and technical-native-receipt.json.
Both are independently rechecked on VPS before writing a delivery receipt.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import zipfile

FAMILIES = ("F12", "F13", "F14", "F16", "F17", "F26")
ARTIFACTS = {
    "F12": {".apk", ".aab"},
    "F13": {".exe"},
    "F14": {".html", ".js"},
    "F16": {".apk", ".aab"},
    "F17": {".exe"},
    "F26": {".onnx"}
}
HEX = re.compile(r"^[0-9a-f]{64}$")

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def actual_format_integrity(family, members):
    """Reject suffix-only pretenders; all checks use bytes in the real archive."""
    native = {name:bytes_ for name,bytes_ in members.items()
              if Path(name).suffix.lower() in ARTIFACTS[family]}
    if family in ("F12","F16"):
        apk = next(v for k,v in native.items() if k.endswith(".apk"))
        aab = next(v for k,v in native.items() if k.endswith(".aab"))
        with zipfile.ZipFile(__import__("io").BytesIO(apk)) as z:
            names = set(z.namelist())
            if not {"AndroidManifest.xml","classes.dex","assets/index.html"}.issubset(names):
                raise RuntimeError("NATIVE_BUNDLE_FAKE_ANDROID_APK")
        with zipfile.ZipFile(__import__("io").BytesIO(aab)) as z:
            names = set(z.namelist())
            if not {"base/manifest/AndroidManifest.xml","base/dex/classes.dex",
                    "base/assets/index.html"}.issubset(names):
                raise RuntimeError("NATIVE_BUNDLE_FAKE_ANDROID_AAB")
        # Emulated runtime evidence is bound to THIS debug APK's exact bytes.
        # Screenshots and software-device tests never confer physical approval.
        proof_raw = members.get("emulator-proof.json")
        shot = members.get("emulator-screen.png")
        if (proof_raw is None) != (shot is None):
            raise RuntimeError("NATIVE_BUNDLE_UNPAIRED_EMULATOR_EVIDENCE")
        if proof_raw is not None:
            proof = json.loads(proof_raw.decode("utf8"))
            fid = family.lower()
            deep_keys = ("webview_dom_runtime_verified",) + (
                ("actual_48_levels_loaded", "next_level_transition_verified",
                 "keyboard_player_movement_verified") if family == "F12" else
                ("inventory_entry_written_in_apk",
                 "inventory_storage_persisted_after_relaunch"))
            if any(proof.get(key) is not True for key in deep_keys):
                raise RuntimeError("ANDROID_DEEP_APK_BEHAVIOR_UNVERIFIED")
            if (proof.get("schema") != "saeit.factory.android-emulated-runtime-check.v1"
                    or proof.get("family") != family
                    or proof.get("package") != "com.zomorodmelal.factory." + fid
                    or proof.get("android_sdk") != 35
                    or proof.get("virtual_device") is not True
                    or proof.get("actual_install_verified") is not True
                    or proof.get("actual_activity_start_verified") is not True
                    or proof.get("real_emulated_touch_and_swipe_dispatched") is not True
                    or proof.get("app_alive_after_interaction") is not True
                    or proof.get("no_app_fatal_crash_observed") is not True
                    or proof.get("physical_device_tested") is not False
                    or proof.get("release_signing_verified") is not False
                    or proof.get("independent_professional_review") is not False
                    or proof.get("quality_1000_certified") is not False
                    or proof.get("commercial_release") is not False
                    or proof.get("apk_sha256") != hashlib.sha256(apk).hexdigest()
                    or proof.get("screenshot_sha256") != hashlib.sha256(shot).hexdigest()
                    or proof.get("emulator_screen_size_bytes") != len(shot)
                    or not isinstance(proof.get("distinct_screen_colors"),int)
                    or proof["distinct_screen_colors"] < 5
                    or not shot.startswith(b"\x89PNG\r\n\x1a\n")):
                raise RuntimeError("NATIVE_BUNDLE_FAKE_OR_MISMATCHED_EMULATOR_RUNTIME")
    elif family in ("F13","F17"):
        data = next(iter(native.values()))
        if (len(data) < 30_000 or data[:2] != b"MZ" or len(data) < 64):
            raise RuntimeError("NATIVE_BUNDLE_FAKE_WINDOWS_EXE")
        offset = int.from_bytes(data[0x3c:0x40],"little")
        if offset < 64 or offset+4 > len(data) or data[offset:offset+4] != b"PE\x00\x00":
            raise RuntimeError("NATIVE_BUNDLE_FAKE_WINDOWS_PE_HEADER")
        if "windows-native-proof.json" in members:
            proof=json.loads(members["windows-native-proof.json"].decode("utf8"))
            row=proof.get("families",{}).get(family,{})
            if (proof.get("schema")!="saeit.factory.windows-native-interactive-acceptance.v1"
                    or proof.get("real_windows_runner_execute") is not True
                    or proof.get("physical_customer_hardware_reviewed") is not False
                    or proof.get("independent_security_expert_approved") is not False
                    or proof.get("quality_1000_certified") is not False
                    or proof.get("public_release") is not False
                    or row.get("sha256")!=hashlib.sha256(data).hexdigest()
                    or (family=="F13" and
                        (row.get("playthroughs_from_actual_exe")!=48
                         or row.get("level_paths_verified")!=48))
                    or (family=="F17" and
                        (row.get("real_packaged_csv_invoices_tested")!=6
                         or row.get("invalid_inventory_rows_rejected")!=9
                         or row.get("exact_decimal_math_verified") is not True))):
                raise RuntimeError("NATIVE_BUNDLE_WINDOWS_RUNTIME_ACCEPTANCE_UNVERIFIED")
    elif family == "F14":
        data = json.loads(members["browser-proof.json"].decode("utf8"))
        if (data.get("actual_chromium_executed") is not True
                or data.get("real_interactive_movement_tested") is not True
                or data.get("keyboard_and_restart_tested") is not True
                or set(data.get("responsive_viewports_tested",[]))!={"desktop","mobile"}
                or data.get("uncaught_js_errors")!=0
                or data.get("external_network_requests")!=0
                or any(hashlib.sha256(members[k]).hexdigest()!=data["source_sha256"][k]
                       for k in ("mini_game.html","game.js"))):
            raise RuntimeError("NATIVE_BUNDLE_F14_REAL_BROWSER_PROOF_FAILED")
    elif family == "F26":
        proof = json.loads(members["native-proof.json"].decode("utf8"))
        if (proof.get("actual_onnxruntime_models_checked")!=48
                or proof.get("holdout_predictions_checked")!=192
                or proof.get("independent_quality_1000_certified") is not False):
            raise RuntimeError("NATIVE_BUNDLE_F26_ONNX_RUNTIME_PROOF_MISSING")
        actual = {name:hashlib.sha256(raw).hexdigest() for name,raw in native.items()}
        declared = {i["file"]:i["sha256"] for i in proof.get("models",[])}
        if actual!=declared or len(actual)!=48:
            raise RuntimeError("NATIVE_BUNDLE_F26_ONNX_BYTES_NOT_CHECKED")
    return True


def pack(family, sources, result, checks):
    if family not in FAMILIES:
        raise RuntimeError("NATIVE_BUNDLE_INVALID_FAMILY")
    if result.exists() or result.is_symlink():
        raise RuntimeError("NATIVE_BUNDLE_DESTINATION_EXISTS")
    if not isinstance(checks, str) or not checks or len(checks) > 300:
        raise RuntimeError("NATIVE_BUNDLE_MISSING_CHECKS")
    if not sources or len(sources) > 60:
        raise RuntimeError("NATIVE_BUNDLE_INVALID_INPUT_COUNT")
    names = [p.name for p in sources]
    if len(set(names)) != len(names):
        raise RuntimeError("NATIVE_BUNDLE_DUPLICATE_BASENAME")
    for source in sources:
        if (source.is_symlink() or not source.is_file() or
                not 0 < source.stat().st_size < 95_000_000 or
                source.name.startswith(".") or
                not re.fullmatch(r"[A-Za-z0-9_.-]{3,96}", source.name)):
            raise RuntimeError("NATIVE_BUNDLE_UNSAFE_INPUT")
    native = [p for p in sources if p.suffix.lower() in ARTIFACTS[family]]
    expected = {"F12": 2, "F13": 1, "F14": 2, "F16": 2, "F17": 1, "F26": 48}[family]
    if len(native) != expected:
        raise RuntimeError("NATIVE_BUNDLE_NATIVE_OUTPUT_COUNT_MISMATCH")
    if family == "F26" and len({p.name for p in native}) != 48:
        raise RuntimeError("NATIVE_BUNDLE_F26_MODEL_COUNT_INVALID")
    actual_format_integrity(family,{p.name:p.read_bytes() for p in sources})
    result.mkdir(mode=0o700, parents=True)
    archive = result / "technical-native-candidate.zip"
    hashes = {}
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for source in sorted(sources, key=lambda x: x.name):
            name = source.name
            contents = source.read_bytes()
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, contents)
            hashes[name] = hashlib.sha256(contents).hexdigest()
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None or set(z.namelist()) != set(hashes):
            raise RuntimeError("NATIVE_BUNDLE_REOPEN_FAILED")
        if any(hashlib.sha256(z.read(name)).hexdigest() != value
               for name,value in hashes.items()):
            raise RuntimeError("NATIVE_BUNDLE_CONTENT_HASH_MISMATCH")
    receipt = {
        "schema": "saeit.factory.private-six-native-candidate.v1",
        "family": family, "format_candidate_count":len(native),
        "checks_executed_in_ci":checks,
        "archive_sha256":digest(archive),
        "archive_members_sha256":hashes,
        "actual_native_file_format_tested_in_ci":True,
        "physical_device_matrix_verified":False,
        "independent_specialist_review_verified":False,
        "quality_1000_certified":False,
        "commercial_release":False,
        "public_transfer":False,
        "owner_signature":None
    }
    (result/"technical-native-receipt.json").write_text(
        json.dumps(receipt,sort_keys=True,indent=2)+"\n",encoding="utf8")
    print("SIX_PRIVATE_NATIVE_RECEIPT="+json.dumps(
        {"family":family, "formats":len(native),"archive_sha256":receipt["archive_sha256"],
         "quality_1000_certified":False},sort_keys=True))
    return receipt

def verify(folder, expected_family):
    if expected_family not in FAMILIES or folder.is_symlink():
        raise RuntimeError("NATIVE_RECEIPT_INVALID_TARGET")
    receipt_file=folder/"technical-native-receipt.json"
    archive=folder/"technical-native-candidate.zip"
    if receipt_file.is_symlink() or archive.is_symlink():
        raise RuntimeError("NATIVE_RECEIPT_SYMLINK")
    receipt=json.loads(receipt_file.read_text(encoding="utf8"))
    if (receipt.get("schema")!="saeit.factory.private-six-native-candidate.v1"
            or receipt.get("family")!=expected_family
            or receipt.get("quality_1000_certified") is not False
            or receipt.get("commercial_release") is not False
            or receipt.get("public_transfer") is not False
            or receipt.get("owner_signature") is not None
            or receipt.get("archive_sha256")!=digest(archive)):
        raise RuntimeError("NATIVE_RECEIPT_POLICY_OR_ARCHIVE_HASH_FAIL")
    files=receipt.get("archive_members_sha256")
    if not isinstance(files,dict) or any(not HEX.fullmatch(v)
                                           for v in files.values()):
        raise RuntimeError("NATIVE_RECEIPT_INVALID_MEMBER_HASHES")
    if archive.stat().st_size > 220_000_000:
        raise RuntimeError("NATIVE_RECEIPT_ARCHIVE_TOO_LARGE")
    with zipfile.ZipFile(archive) as z:
        info=z.infolist()
        if (len(info)!=len(files) or sum(i.file_size for i in info)>300_000_000
                or set(z.namelist())!=set(files)
                or z.testzip() is not None
                or any(i.is_dir() or i.flag_bits & 1 or i.file_size > 95_000_000 or
                       ((i.external_attr >> 16)&0o170000)==0o120000 for i in info)):
            raise RuntimeError("NATIVE_RECEIPT_ZIP_INVALID")
        for name,value in files.items():
            if not re.fullmatch(r"[A-Za-z0-9_.-]{3,96}",name):
                raise RuntimeError("NATIVE_RECEIPT_UNSAFE_FILENAME")
            if hashlib.sha256(z.read(name)).hexdigest()!=value:
                raise RuntimeError("NATIVE_RECEIPT_MEMBER_MISMATCH")
    with zipfile.ZipFile(archive) as z:
        actual_format_integrity(expected_family,{name:z.read(name) for name in files})
    actual=[name for name in files if Path(name).suffix.lower() in ARTIFACTS[expected_family]]
    expected={"F12":2,"F13":1,"F14":2,"F16":2,"F17":1,"F26":48}[expected_family]
    if len(actual)!=expected or receipt.get("format_candidate_count")!=expected:
        raise RuntimeError("NATIVE_RECEIPT_FALSE_NATIVE_COUNT")
    return {"family":expected_family,"native_count":expected,
            "archive_sha256":receipt["archive_sha256"],
            "private_only":True,"quality_1000":False}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--family",choices=FAMILIES,required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--file",action="append",default=[])
    p.add_argument("--checks",default="")
    p.add_argument("--verify",action="store_true")
    a=p.parse_args()
    if a.verify:
        print("SIX_NATIVE_INDEPENDENT_VERIFICATION="+json.dumps(
            verify(Path(a.out),a.family),sort_keys=True))
    else:
        pack(a.family,[Path(x) for x in a.file],Path(a.out),a.checks)
