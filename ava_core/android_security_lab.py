"""Offline, owner-scoped Android security training inside the single bot.

This capability DOES NOT connect to a handset, execute APKs, collect real
messages/photos, send network requests, or grant remote control. The host must
authenticate the canonical bot owner before exposing this adapter.
"""
from __future__ import annotations

import base64
import binascii
from hashlib import sha256, pbkdf2_hmac
from hmac import compare_digest
from io import BytesIO
import json
import re
from zipfile import BadZipFile, ZipFile

from .capabilities import ActionRequest, AdapterResult, CapabilitySpec, OperationSpec


NAME = "owner_android_security_lab"
SPEC = CapabilitySpec(NAME, (
    OperationSpec("status", "read"),
    OperationSpec("simulate_authentication", "read"),
    OperationSpec("export_synthetic_messages", "read"),
    OperationSpec("inspect_device_report", "read"),
    OperationSpec("triage_apk", "read"),
    OperationSpec("training_lessons", "read"),
    OperationSpec("training_case", "read"),
    OperationSpec("training_quiz", "read"),
))

# These are examples, NOT messages taken from any person's device.
DEMO_MESSAGES = (
    {"id": 1, "sender": "TRAINING_ONLY", "text": "Synthetic sign-in notification"},
    {"id": 2, "sender": "TRAINING_ONLY", "text": "Synthetic store receipt"},
    {"id": 3, "sender": "TRAINING_ONLY", "text": "Synthetic appointment reminder"},
)
REPORT_FIELDS = (
    "manufacturer", "model", "android_release", "sdk", "security_patch",
    "vendor_patch", "build_type", "verified_boot",
    "bootloader_locked", "storage_encryption", "debuggable",
)
PERMISSIONS = (
    "android.permission.READ_SMS",
    "android.permission.READ_CALL_LOG",
    "android.permission.READ_CONTACTS",
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.RECORD_AUDIO",
    "android.permission.CAMERA",
    "android.permission.REQUEST_INSTALL_PACKAGES",
    "android.permission.QUERY_ALL_PACKAGES",
    "android.permission.SYSTEM_ALERT_WINDOW",
)
MAX_BASE64_CHARS = 12_000_000  # ~9 MB compressed APK limit.
MAX_UNCOMPRESSED_BYTES = 40_000_000
MAX_ENTRIES = 2000
MAX_MANIFEST_BYTES = 1_000_000


def _success(data: dict) -> AdapterResult:
    return AdapterResult(True, json.dumps(data, ensure_ascii=False, sort_keys=True))


def _inspect_device_report(arguments) -> AdapterResult:
    report = arguments.get("report")
    if not isinstance(report, dict) and not hasattr(report, "get"):
        raise ValueError("Explicit owner-supplied report mapping required")
    if len(report) > 30:
        raise ValueError("Unexpectedly large report")
    # Never accept contact lists, phone numbers, photo paths or message content.
    filtered = {}
    for key in REPORT_FIELDS:
        value = report.get(key)
        if value is not None:
            if type(value) is not str or len(value) > 80:
                raise ValueError("Invalid security-report field")
            filtered[key] = value
    if not filtered:
        raise ValueError("No supported security fields in report")
    return _success({
        "source": "owner_supplied_local_report",
        "verified_against_device": False,
        "fields": filtered,
        "network_requests": 0,
    })


def _triage_apk(arguments) -> AdapterResult:
    encoded = arguments.get("apk_base64")
    if type(encoded) is not str or not 0 < len(encoded) <= MAX_BASE64_CHARS:
        raise ValueError("Provide a bounded, owner-supplied base64 APK")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Invalid base64 APK") from exc
    try:
        with ZipFile(BytesIO(raw), "r") as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ENTRIES or sum(i.file_size for i in infos) > MAX_UNCOMPRESSED_BYTES:
                raise ValueError("APK exceeds safe offline inspection limits")
            entries = {i.filename: i for i in infos}
            manifest_info = entries.get("AndroidManifest.xml")
            permissions: list[str] = []
            manifest_format = "missing"
            if manifest_info is not None:
                if manifest_info.file_size > MAX_MANIFEST_BYTES:
                    raise ValueError("Manifest too large")
                manifest = archive.read(manifest_info)
                if manifest.lstrip().startswith((b"<manifest", b"<?xml")):
                    manifest_format = "plain_xml_partial_scan"
                    xml = manifest.decode("utf-8", errors="replace")
                    # Strictly advisory: a compiled binary XML manifest is not
                    # decoded by this lightweight, zero-dependency inspector.
                    permissions = sorted({
                        item for item in PERMISSIONS
                        if re.search(
                            r'<uses-permission(?:-sdk-23)?\b[^>]{0,500}'
                            r'android:name\s*=\s*["\x27]' + re.escape(item) + r'["\x27]',
                            xml,
                        )
                    })
                else:
                    manifest_format = "compiled_xml_not_parsed"
            result = {
                "apk_sha256": sha256(raw).hexdigest(),
                "archive_entries": len(infos),
                "manifest_format": manifest_format,
                "detected_permissions": permissions,
                "permissions_analysis_complete": False,
                "executed_apk": False,
                "network_requests": 0,
                "warning": "Permission indicators are not evidence of spyware.",
            }
            return _success(result)
    except BadZipFile as exc:
        raise ValueError("Invalid APK ZIP structure") from exc


def security_lab_adapter(request: ActionRequest) -> AdapterResult:
    if request.capability != NAME:
        raise PermissionError("Wrong capability identity")
    if request.operation == "status":
        return _success({
            "identity": "mojtaba.bot.ai",
            "mode": "offline_owner_only",
            "operations": [op.name for op in SPEC.operations],
            "device_connection": False, "remote_control": False,
            "real_message_collection": False, "network_requests": 0,
        })
    if request.operation == "simulate_authentication":
        # Fictional credentials: no brute-force, accounts or external systems.
        secret = b"synthetic-training-secret"
        salt = b"owner-demo-salt!"
        digest = pbkdf2_hmac("sha256", secret, salt, 120_000)
        correct = compare_digest(digest, pbkdf2_hmac("sha256", secret, salt, 120_000))
        rejected = not compare_digest(digest, pbkdf2_hmac("sha256", b"wrong-demo", salt, 120_000))
        return _success({"synthetic_valid_accepted": correct, "synthetic_wrong_rejected": rejected})
    if request.operation == "export_synthetic_messages":
        return _success({"synthetic": True, "messages": DEMO_MESSAGES})
    if request.operation == "inspect_device_report":
        return _inspect_device_report(request.arguments)
    if request.operation == "triage_apk":
        return _triage_apk(request.arguments)
    if request.operation in ("training_lessons", "training_case", "training_quiz"):
        from .android_security_training import list_lessons, run_synthetic_case, quiz
        if request.operation == "training_lessons":
            return _success(list_lessons())
        if request.operation == "training_case":
            return _success(run_synthetic_case(request.arguments))
        return _success(quiz(request.arguments))
    raise ValueError("Undeclared security lab operation")


def security_lab_capability():
    """Trusted host may opt in; importing this module starts no worker."""
    return SPEC, security_lab_adapter
