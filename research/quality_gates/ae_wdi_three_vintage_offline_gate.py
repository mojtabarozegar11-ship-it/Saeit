#!/usr/bin/env python3
"""AE-2026-001: verify OFFLINE official WDI archive bytes before historical comparison.

No download, no external dependencies, no benchmark, no inferred historical values.
Usage: python ae_wdi_three_vintage_offline_gate.py /private/wdi_manifest.json
Manifest: {"releases":[{"id":"2024-12-16","source_url":"...","resolved_url":"...", "path":"...",
"sha256":"64 hex chars","bytes":12345,"retrieved_utc":"2026-10-29T00:00:00Z"}, ...]}
The SHA-256 and byte counts must come from independently downloaded REAL files.
"""
import datetime
import hashlib
import json
import pathlib
import re
import sys
import zipfile

OFFICIAL = {
    "2024-12-16": "https://databank.worldbank.org/data/download/Archive/WDI_excel_2024_12_16.zip",
    "2025-12-19": "https://databank.worldbank.org/data/download/Archive/WDI_excel_2025_12_19.zip",
    "2026-10-08": "https://databankfiles.worldbank.org/public/ddpext_download/Archive/WDI_EXCEL_2026_10_08.zip",
}
# The World Bank archive index links (source_url) are not the redirected file URLs.
# Pin both endpoints; a successful ZIP checksum alone cannot establish the retrieval origin.
FINAL_OFFICIAL = {
    "2024-12-16": "https://databankfiles.worldbank.org/public/ddpext_download/Archive/WDI_excel_2024_12_16.zip",
    "2025-12-19": "https://databankfiles.worldbank.org/public/ddpext_download/Archive/WDI_excel_2025_12_19.zip",
    "2026-10-08": "https://databankfiles.worldbank.org/public/ddpext_download/Archive/WDI_EXCEL_2026_10_08.zip",
}
MAX_UNCOMPRESSED = 3 * 1024**3

class EvidenceGateError(ValueError):
    pass

def verify(manifest):
    manifest = pathlib.Path(manifest).resolve()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    releases = data.get("releases") if isinstance(data, dict) else None
    if not isinstance(releases, list) or len(releases) != 3:
        raise EvidenceGateError("Exactly three official releases required")
    if {r.get("id") for r in releases if isinstance(r, dict)} != set(OFFICIAL):
        raise EvidenceGateError("Missing/duplicate/unexpected WDI release")
    result = []
    for record in releases:
        release = record["id"]
        if record.get("source_url") != OFFICIAL[release]:
            raise EvidenceGateError("Official source URL mismatch: " + release)
        if record.get("resolved_url") != FINAL_OFFICIAL[release]:
            raise EvidenceGateError("Official redirect/final URL mismatch: " + release)
        stamp = record.get("retrieved_utc")
        if not isinstance(stamp, str) or not stamp.endswith("Z"):
            raise EvidenceGateError("UTC retrieval timestamp missing: " + release)
        try:
            datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise EvidenceGateError("Invalid retrieval timestamp: " + release) from exc
        digest = record.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            raise EvidenceGateError("Real SHA-256 required: " + release)
        expected_bytes = record.get("bytes")
        if type(expected_bytes) is not int or expected_bytes <= 0:
            raise EvidenceGateError("Positive original byte count required: " + release)
        raw = record.get("path")
        if not isinstance(raw, str) or not raw:
            raise EvidenceGateError("Private archive path missing: " + release)
        p = pathlib.Path(raw).expanduser()
        if not p.is_absolute():
            p = manifest.parent / p
        if not p.is_file() or p.stat().st_size != expected_bytes:
            raise EvidenceGateError("Missing/size-mismatched original ZIP: " + release)
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1024*1024), b""):
                h.update(chunk)
        if h.hexdigest().lower() != digest.lower():
            raise EvidenceGateError("Original archive SHA-256 mismatch: " + release)
        try:
            with zipfile.ZipFile(p) as z:
                infos = z.infolist()
                names = [i.filename for i in infos]
                if not infos or len(names) != len(set(names)):
                    raise EvidenceGateError("Empty/duplicate ZIP entries: " + release)
                if any(i.flag_bits & 1 for i in infos):
                    raise EvidenceGateError("Encrypted ZIP entry: " + release)
                if any(n.startswith("/") or ".." in pathlib.PurePosixPath(n).parts or "\\" in n for n in names):
                    raise EvidenceGateError("Unsafe ZIP entry path: " + release)
                if sum(i.file_size for i in infos) > MAX_UNCOMPRESSED:
                    raise EvidenceGateError("Archive uncompressed size exceeds safety cap: " + release)
                sheets = [n for n in names if n.lower().endswith((".xlsx", ".xls"))]
                if not sheets:
                    raise EvidenceGateError("No Excel workbook inside official archive: " + release)
                if z.testzip() is not None:
                    raise EvidenceGateError("ZIP CRC failure: " + release)
        except (zipfile.BadZipFile, OSError) as exc:
            raise EvidenceGateError("Corrupt/unreadable archive: " + release) from exc
        result.append({"release": release, "bytes": expected_bytes,
                       "sha256": h.hexdigest(), "source_url": OFFICIAL[release], "resolved_url": FINAL_OFFICIAL[release], "workbooks": sheets})
    return {"state": "ARCHIVE_INTEGRITY_ONLY_NOT_HISTORICAL_BENCHMARK",
            "releases": result,
            "remaining": ["verify workbook series/base-year metadata",
                          "extract historical country-year values",
                          "run fixed-cohort benchmark",
                          "verify independent ILOSTAT vintage"]}

if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise EvidenceGateError("Usage: script.py /private/wdi_manifest.json")
        print(json.dumps(verify(sys.argv[1]), indent=2))
    except (EvidenceGateError, ValueError, OSError, KeyError, TypeError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        sys.exit(2)
