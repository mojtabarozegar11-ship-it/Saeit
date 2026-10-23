#!/usr/bin/env python3
"""Evidence-gated public research registry updater (cPanel-side, stdlib only).

Input must be a private, explicitly publication-approved manifest. This tool
never invents research projects, leaders, methods, audits, or results. It
writes only the public sanitized JSON after strict validation.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

ID = re.compile(r"^ZM-RD-(20[2-9][0-9])-[0-9]{4}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
DATE = re.compile(r"^20[0-9]{2}-[0-9]{2}-[0-9]{2}$")
STATUS = {"registered", "in_progress", "analysis", "completed", "published"}
DOMAINS = {"genetics", "plant_breeding", "animal_breeding", "bioinformatics",
           "microbiology", "functional_food", "agricultural_economics", "other"}
FIELDS = {"id", "title", "domain", "lead", "method", "status", "updated_on",
          "evidence", "publication_permission", "summary"}
EVIDENCE_FIELDS = {"title", "url", "sha256"}
APPROVAL_FIELDS = {"authorized_by", "record_id", "approved_on"}
MAX_APPROVED_PROJECTS = 5000  # includes the reported 1,457 historical projects if substantiated

def nonempty(value: object, field: str, min_len: int = 2, max_len: int = 350) -> str:
    assert isinstance(value, str), f"{field} must be text"
    clean = value.strip()
    assert min_len <= len(clean) <= max_len, f"{field} length invalid"
    assert not any(ord(char) < 32 for char in clean), f"{field} control char"
    return clean

def date(value: object, label: str) -> str:
    value = nonempty(value, label, 10, 10)
    assert DATE.fullmatch(value), f"{label} format"
    dt.date.fromisoformat(value)
    return value

def verify_url(value: object) -> str:
    value = nonempty(value, "evidence url", 12, 1200)
    parts = urlsplit(value)
    assert parts.scheme == "https" and parts.netloc and not parts.username and not parts.password
    assert parts.hostname and not parts.hostname.endswith(".local")
    assert not parts.fragment or len(parts.fragment) < 120
    return value

def clean_project(entry: object) -> dict:
    assert isinstance(entry, dict) and set(entry) == FIELDS, "project fields differ from public schema"
    key = nonempty(entry["id"], "id", 15, 15)
    assert ID.fullmatch(key), "invalid project id"
    status = nonempty(entry["status"], "status")
    domain = nonempty(entry["domain"], "domain")
    assert status in STATUS and domain in DOMAINS
    approval = entry["publication_permission"]
    assert isinstance(approval, dict) and set(approval) == APPROVAL_FIELDS
    clean_approval = {
        "authorized_by": nonempty(approval["authorized_by"], "authorized_by", 3, 140),
        "record_id": nonempty(approval["record_id"], "approval reference", 4, 160),
        "approved_on": date(approval["approved_on"], "approved_on"),
    }
    evidence = entry["evidence"]
    assert isinstance(evidence, list) and 1 <= len(evidence) <= 20, "evidence required"
    clean_evidence = []
    for ev in evidence:
        assert isinstance(ev, dict) and set(ev) == EVIDENCE_FIELDS
        value = nonempty(ev["sha256"], "evidence hash", 64, 64)
        assert SHA.fullmatch(value), "sha256 invalid"
        clean_evidence.append({
            "title": nonempty(ev["title"], "evidence title", 3, 140),
            "url": verify_url(ev["url"]),
            "sha256": value,
        })
    return {
        "id": key,
        "title": nonempty(entry["title"], "title", 8, 180),
        "domain": domain,
        "lead": nonempty(entry["lead"], "lead", 4, 140),
        "method": nonempty(entry["method"], "method", 40, 2500),
        "status": status,
        "updated_on": date(entry["updated_on"], "updated_on"),
        "summary": nonempty(entry["summary"], "summary", 40, 700),
        "evidence": clean_evidence,
        "publication_permission": clean_approval,
    }

def safe_source(raw: str) -> Path:
    home = Path.home().resolve()
    public = home / "public_html"
    source = Path(raw)
    assert source.is_absolute() and source.is_file() and not source.is_symlink()
    final = source.resolve()
    assert final.is_relative_to(home) and not final.is_relative_to(public.resolve())
    assert source.stat().st_size <= 4_000_000, "manifest too large"
    return source

def validate(raw: str) -> list[dict]:
    source = safe_source(raw)
    package = json.loads(source.read_text(encoding="utf-8"))
    assert isinstance(package, dict) and set(package) == {"schema_version", "projects"}
    assert package["schema_version"] == 1
    entries = package["projects"]
    assert isinstance(entries, list) and len(entries) <= MAX_APPROVED_PROJECTS
    clean = [clean_project(item) for item in entries]
    keys = [entry["id"] for entry in clean]
    assert len(keys) == len(set(keys)), "duplicate project ID"
    assert clean, "No approved project data; refuse to replace public registry with empty set"
    return clean

def publish(source: str):
    projects = validate(source)
    home = Path.home()
    path = home / "public_html" / "research" / "projects" / "projects.json"
    assert path.is_file() and not path.is_symlink(), "registry not installed"
    audit_folder = home / ".backups" / "zomorod-research-registry-entries"
    audit_folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = home / ".zm-research-registry-update.lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        previous = path.read_bytes()
        package = {"schema_version": 1,
                   "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                   "verification_notice": "Information and evidence submitted by the company; independent validation must be assessed separately.",
                   "projects": projects}
        new = (json.dumps(package, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive = audit_folder / f"projects-{stamp}-{hashlib.sha256(previous).hexdigest()[:10]}.json"
        with archive.open("xb") as saved:
            saved.write(previous)
            saved.flush()
            os.fsync(saved.fileno())
        temporary = path.with_name(".projects-registry-next.json")
        assert not temporary.exists()
        with temporary.open("xb") as f:
            f.write(new)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
        assert path.read_bytes() == new
    print(f"RESEARCH_REGISTRY_PUBLISHED_PROJECTS={len(projects)}")
    print("PREVIOUS_VERSION_ARCHIVED=yes")

def selftest():
    base = {
        "id": "ZM-RD-2026-0001", "title": "نمونه ساختاری برای آزمون اعتبارسنجی",
        "domain": "genetics", "lead": "مسئول آزمون نرم‌افزار",
        "method": "این متن صرفاً داده ساختگی آزمون محلی است و هرگز در وب‌سایت به عنوان پروژه واقعی منتشر نخواهد شد.",
        "status": "registered", "updated_on": "2026-10-23",
        "summary": "این رکورد صرفاً برای آزمون صحت فیلدها و محافظت در برابر انتشار نامعتبر ایجاد شده است.",
        "evidence": [{"title": "مدرک نمونه آزمون",
                      "url": "https://example.org/research/temporary",
                      "sha256": "a" * 64}],
        "publication_permission": {"authorized_by": "مسئول آزمون", "record_id": "test-only-0001", "approved_on": "2026-10-23"},
    }
    assert clean_project(base)["id"] == base["id"]
    for field, invalid in [
        ("id", "invalid"), ("lead", ""), ("method", "بدون روش"),
        ("status", "peer_reviewed"), ("evidence", []),
    ]:
        variant = dict(base)
        variant[field] = invalid
        try:
            clean_project(variant)
        except (AssertionError, ValueError):
            pass
        else:
            raise AssertionError(f"invalid field accepted: {field}")
    approved_example = [dict(base, id=f"ZM-RD-2026-{i:04d}") for i in range(1, 1458)]
    assert len(approved_example) == 1457
    assert len({clean_project(item)["id"] for item in approved_example}) == 1457
    print("RESEARCH_REGISTRY_1457_CAPACITY_SELFTEST=passed")
    print("RESEARCH_REGISTRY_UPDATER_SELFTEST=passed")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["selftest", "validate", "publish"])
    p.add_argument("--source", default="")
    args = p.parse_args()
    if args.command == "selftest":
        selftest()
    elif args.command == "validate":
        print(f"RESEARCH_REGISTRY_VALID_PROJECTS={len(validate(args.source))}")
    else:
        publish(args.source)
