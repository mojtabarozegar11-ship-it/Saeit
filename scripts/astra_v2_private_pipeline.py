#!/usr/bin/env python3
"""Astra 2.0 private, continuous-capable R&D manufacturing queue.

Isolated sandbox implementation: only allowlisted, reviewed source builders;
NO market claims, paid APIs, public store, cPanel/site DB, external network,
payments or automatic approval. The queue can process new internal briefs
continuously when eligible briefs exist; it does not invent new briefs or
pretend rechecking the same ZIP is new production. Not installed on VPS.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "product_prototypes" / "orchard_decision_audit"
FILES = (
    "decision_audit.py", "serve_local.py", "app.js",
    "index.html", "style.css", "example_synthetic.json", "README.md", "self_test.py",
)
TEST_NAME = "test_astra_orchard_decision_audit.py"
BUILDER = "orchard_decision_audit_v2"
PROCUREMENT_BUILDER = "farm_procurement_audit_v1"
WATER_BUILDER = "farm_water_land_margin_audit_v1"
WATER_ROOT = ROOT / "product_prototypes" / "farm_water_land_margin_audit"
WATER_FILES = (
    "water_margin_audit.py", "render_report.py", "example_synthetic.json",
    "self_test.py", "README.md",
)
PROCUREMENT_ROOT = ROOT / "product_prototypes" / "farm_procurement_audit"
PROCUREMENT_FILES = (
    "procurement_audit.py", "render_report.py", "example_synthetic.json",
    "self_test.py", "README.md",
)
BUILDERS = {
    BUILDER: {
        "root": PROTOTYPE, "files": FILES, "test": TEST_NAME,
        "slug": "orchard_decision_audit", "title": "Orchard Investment Decision Audit",
    },
    PROCUREMENT_BUILDER: {
        "root": PROCUREMENT_ROOT, "files": PROCUREMENT_FILES,
        "test": "test_astra_farm_procurement_audit.py",
        "slug": "farm_procurement_audit", "title": "Farm Input Procurement Quote Audit",
    },
    WATER_BUILDER: {
        "root": WATER_ROOT, "files": WATER_FILES,
        "test": "test_astra_farm_water_land_margin_audit.py",
        "slug": "farm_water_land_margin_audit",
        "title": "Farm Water and Land Margin Audit",
    },
}
MAX_BRIEFS = 1000

SCHEMA = """
PRAGMA journal_mode=DELETE;
CREATE TABLE IF NOT EXISTS jobs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 brief_id TEXT NOT NULL,
 builder TEXT NOT NULL,
 payload_sha TEXT NOT NULL UNIQUE,
 stage TEXT NOT NULL DEFAULT 'QUEUED',
 attempts INTEGER NOT NULL DEFAULT 0,
 artifact_sha TEXT,
 manifest_sha TEXT,
 last_error TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL,
 completed_at TEXT
);
CREATE INDEX IF NOT EXISTS jobs_stage_id ON jobs(stage,id);
"""


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def safe_root(path):
    target = Path(path).expanduser()
    if target.is_symlink():
        raise ValueError("root symlinks forbidden")
    target = target.resolve()
    if target == Path("/") or str(target) in ("/home", "/tmp"):
        raise ValueError("root is too broad")
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(target, 0o700)
    return target


def reportable_path(root, relative):
    out = root / relative
    if out.is_symlink() or out.resolve().parent != root.resolve():
        raise ValueError("path escapes private workspace")
    return out


def check_brief(obj):
    if not isinstance(obj, dict) or set(obj) != {
        "brief_id", "builder", "development_scope", "publication_allowed",
        "market_demand_verified", "paid_api_budget", "problem",
    }:
        raise ValueError("exactly seven product brief fields required")
    key = obj["brief_id"]
    if not isinstance(key, str) or not re.fullmatch("[a-z][a-z0-9_-]{2,63}", key):
        raise ValueError("invalid brief_id")
    if obj["builder"] not in BUILDERS:
        raise ValueError("no verified builder registered")
    if obj["development_scope"] != "private_reference_prototype":
        raise ValueError("only private reference prototype builds permitted")
    if obj["publication_allowed"] is not False:
        raise ValueError("publication may not be authorized here")
    if obj["market_demand_verified"] is not False:
        raise ValueError("self-declared market verification forbidden")
    if type(obj["paid_api_budget"]) is not int or obj["paid_api_budget"] != 0:
        raise ValueError("no paid API budget in prototype builder")
    if not isinstance(obj["problem"], str) or not 20 <= len(obj["problem"]) <= 500:
        raise ValueError("specific, bounded customer-problem statement required")
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


@contextmanager
def locked(root):
    handle = (root / ".queue.lock").open("a+b")
    os.chmod(root / ".queue.lock", 0o600)
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


@contextmanager
def database(root):
    db = root / "queue.sqlite3"
    if db.is_symlink():
        raise ValueError("db path symlink")
    db_preexisting = db.exists()
    con = sqlite3.connect(str(db), timeout=15)
    if not db_preexisting:
        os.chmod(db, 0o600)
    con.executescript(SCHEMA)
    try:
        yield con
    finally:
        con.close()


def enqueue(root, obj):
    payload = check_brief(obj)
    ident = digest(payload)
    with locked(root), database(root) as conn:
        existing = conn.execute(
            "SELECT id,stage FROM jobs WHERE payload_sha=?", (ident,)).fetchone()
        if existing:
            return {"job_id": existing[0], "status": "UNCHANGED",
                    "stage": existing[1], "new_job": False}
        rows = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        if rows >= MAX_BRIEFS:
            raise ValueError("private queue at bounded capacity")
        with conn:
            cur = conn.execute(
                """INSERT INTO jobs(brief_id,builder,payload_sha,stage,created_at)
                   VALUES (?,?,?,?,?)""",
                (obj["brief_id"], obj["builder"], ident, "QUEUED", now()))
        return {"job_id": cur.lastrowid, "status": "QUEUED", "new_job": True}


def _validate_sources(builder=BUILDER):
    config = BUILDERS[builder]
    for f in config["files"]:
        path = config["root"] / f
        if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
            raise ValueError("missing or unsafe product source " + f)
    test = ROOT / "tests" / config["test"]
    if test.is_symlink() or not test.is_file():
        raise ValueError("required independent QA tests missing")
    return test


def _test_reference(builder=BUILDER):
    _validate_sources(builder)
    config = BUILDERS[builder]
    cmd = [sys.executable, "-m", "unittest", "discover",
           "-s", str(ROOT / "tests"), "-p", config["test"], "-v"]
    process = subprocess.run(cmd, cwd=str(ROOT), timeout=100,
                             capture_output=True, text=True,
                             env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"})
    if process.returncode != 0 or "OK" not in process.stderr:
        raise RuntimeError("QA_REGRESSION_FAILURE")
    return process


def _make_artifact(root, job_id, builder=BUILDER):
    _test_reference(builder)
    config = BUILDERS[builder]
    versions = [(name, (config["root"] / name).read_bytes())
                for name in config["files"]]
    source_sha = digest(builder.encode() + b"".join(
        name.encode() + b"\x00" + digest(blob).encode() for name, blob in versions))
    staged_fd, staged_path = tempfile.mkstemp(prefix=".prototype-", suffix=".zip", dir=root)
    os.close(staged_fd)
    temp = Path(staged_path)
    destination = root / ("artifact-" + source_sha + ".zip")
    if destination.is_symlink():
        raise ValueError("artifact path symlink forbidden")
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for name, data in sorted(versions):
                member = zipfile.ZipInfo(config["slug"] + "/" + name,
                                          date_time=(2020,1,1,0,0,0))
                member.compress_type=zipfile.ZIP_DEFLATED
                member.external_attr=0o100644 << 16
                z.writestr(member, data)
        with zipfile.ZipFile(temp) as z:
            if z.testzip() is not None or len(z.namelist()) != len(config["files"]):
                raise ValueError("ZIP_INTEGRITY_FAILURE")
        os.chmod(temp, 0o600)
        if destination.exists():
            if digest(destination.read_bytes()) != digest(temp.read_bytes()):
                raise RuntimeError("IMMUTABLE_ARTIFACT_CONFLICT")
        else:
            os.link(temp, destination)
        data = destination.read_bytes()
        report = {
            "schema_version": 1,
            "source_builder": builder,
            "product_slug": config["slug"],
            "prototype_name": config["title"],
            "development_scope": "private_reference_prototype",
            "artifact_sha256": digest(data),
            "source_digest": source_sha,
            "included_files": sorted(config["files"]),
            "technical_regression": "PASSED",
            "integrity_check": "PASSED",
            "quality_score": None,
            "commercial_product": False,
            "sale_ready": False,
            "qualified_market_opportunity": False,
            "evidence_of_willingness_to_pay": False,
            "independent_domain_review": False,
            "ux_user_study": False,
            "rights_and_support_review": False,
            "owner_publication_approval": False,
            "public_deployment_allowed": False,
            "real_payment_allowed": False,
            "no_live_site_changes": True,
            "blocking_gates": [
                "MARKET_DEMAND_NOT_VERIFIED",
                "DOMAIN_REVIEW_MISSING",
                "USER_STUDY_MISSING",
                "ACCESSIBILITY_REVIEW_MISSING",
                "RIGHTS_SUPPORT_REVIEW_MISSING",
                "OWNER_RELEASE_GRANT_MISSING",
            ],
        }
        manifest = json.dumps(report, sort_keys=True, indent=2).encode() + b"\n"
        manifest_path = root / ("qa-" + source_sha + ".json")
        if not manifest_path.exists():
            fd, tmp = tempfile.mkstemp(prefix=".qa-", dir=root)
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(manifest);f.flush();os.fsync(f.fileno())
                os.chmod(tmp, 0o600)
                os.link(tmp, manifest_path)
            finally:
                if os.path.exists(tmp):os.unlink(tmp)
        elif manifest_path.read_bytes()!=manifest:
            raise RuntimeError("IMMUTABLE_MANIFEST_CONFLICT")
        return report["artifact_sha256"], digest(manifest), source_sha
    finally:
        if temp.exists():temp.unlink()


def intake_private_briefs(root):
    """Collect capped local-only proto briefs. No network, buyer claims or publication.

    Work arrives only when an external reviewed process writes an allowlisted
    JSON brief into the private inbox. Re-scans are idempotent by payload SHA.
    An invalid inbox file is recorded as a count and never blocks healthy work.
    """
    inbox = root / "incoming"
    if not inbox.exists():
        return {"accepted":0,"unchanged":0,"rejected":0}
    if inbox.is_symlink() or not inbox.is_dir():
        raise ValueError("private inbox must be a regular directory")
    entries = sorted(inbox.iterdir(),key=lambda p:p.name)
    if len(entries) > MAX_BRIEFS:
        raise ValueError("private inbox exceeds bounded entry count")
    counts={"accepted":0,"unchanged":0,"rejected":0}
    for item in entries:
        if not item.name.endswith(".json") or item.is_symlink() or not item.is_file():
            counts["rejected"] += 1
            continue
        try:
            if item.stat().st_size > 20000:
                raise ValueError("oversized private brief")
            obj=json.loads(item.read_text(encoding="utf-8"))
            result=enqueue(root,obj)
            counts["accepted" if result["new_job"] else "unchanged"]+=1
        except (OSError,ValueError,TypeError,UnicodeDecodeError):
            counts["rejected"]+=1
    return counts


def _self_directed_cycle(root):
    """Autonomously create one new *educational case edition* each UTC hour.

    This runs under the same queue lock, not through the external inbox. It
    does not count as a new commercial product or verified market research.
    """
    name=ROOT/"scripts"/"astra_v2_self_directed_education.py"
    if name.is_symlink() or not name.is_file():
        return {"status":"MODULE_MISSING","new_private_educational_edition":False}
    spec=importlib.util.spec_from_file_location("astra_self_directed_education",str(name))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.create_current(root)


def tick(root):
    intake_private_briefs(root)
    with locked(root), database(root) as conn:
        try:
            autonomous=_self_directed_cycle(root)
        except (OSError,ValueError,AssertionError,RuntimeError,zipfile.BadZipFile):
            autonomous={"status":"CASE_REVIEW_REQUIRED",
                        "new_private_educational_edition":False}
        # The EXCLUSIVE file lock remains held for the full build. Therefore
        # any BUILDING job seen *after* acquiring it was abandoned by a
        # terminated worker, not concurrently running. Recover at most twice;
        # never retry owner/policy blockers or unknown historical factory jobs.
        interrupted = conn.execute(
            "SELECT id, attempts FROM jobs WHERE stage='BUILDING' ORDER BY id"
        ).fetchall()
        with conn:
            for lost_id, used_attempts in interrupted:
                if used_attempts < 3:
                    conn.execute(
                        """UPDATE jobs SET stage='QUEUED',
                           last_error='INTERRUPTED_REQUEUED' WHERE id=?""",
                        (lost_id,))
                else:
                    conn.execute(
                        """UPDATE jobs SET stage='FAILED_REVIEW',
                           last_error='RETRY_LIMIT_EXCEEDED' WHERE id=?""",
                        (lost_id,))
        row=conn.execute(
            "SELECT id,brief_id,builder,stage,attempts FROM jobs "
            "WHERE stage='QUEUED' ORDER BY id LIMIT 1").fetchone()
        if not row:
            return {"status":"NO_ELIGIBLE_WORK", "new_products":0,
                    "autonomous_education":autonomous,
                    "note":"no queued specialist builds; educational editions are separate from commercial products"}
        job_id, brief_id, builder, _, attempts = row
        if builder not in BUILDERS:
            raise ValueError("job builder not allowlisted")
        with conn:
            conn.execute(
                "UPDATE jobs SET stage='BUILDING',attempts=attempts+1 WHERE id=?",
                (job_id,))
        try:
            artifact_sha, manifest_sha, version = _make_artifact(root, job_id, builder)
            with conn:
                conn.execute(
                    """UPDATE jobs SET stage='PRIVATE_QA_PASSED',artifact_sha=?,
                       manifest_sha=?,completed_at=?,last_error='' WHERE id=?""",
                    (artifact_sha,manifest_sha,now(),job_id))
            # Count one newly completed job, not a publication or a new distinct
            # product family. Different jobs can reuse one immutable artifact.
            already=conn.execute(
                """SELECT COUNT(*) FROM jobs
                   WHERE artifact_sha=? AND stage='PRIVATE_QA_PASSED'""",
                (artifact_sha,)).fetchone()[0]
            return {"status":"PRIVATE_QA_PASSED","job_id":job_id,
                    "artifact_sha256":artifact_sha,"source_digest":version,
                    "new_distinct_product_versions":int(already==1),
                    "new_products_for_sale":0,"qa_score":None,
                    "autonomous_education":autonomous}
        except (OSError,ValueError,subprocess.SubprocessError,RuntimeError) as exc:
            with conn:
                conn.execute("UPDATE jobs SET stage='FAILED_REVIEW',last_error=? WHERE id=?",
                             (type(exc).__name__,job_id))
            return {"status":"FAILED_REVIEW","job_id":job_id,
                    "error_type":type(exc).__name__,"new_products":0,
                    "autonomous_education":autonomous}


def status(root):
    with locked(root), database(root) as conn:
        rows=conn.execute("SELECT stage,COUNT(*) FROM jobs GROUP BY stage ORDER BY stage").fetchall()
        count=conn.execute(
            "SELECT COUNT(DISTINCT artifact_sha) FROM jobs WHERE stage='PRIVATE_QA_PASSED'"
        ).fetchone()[0]
        family_count=conn.execute(
            "SELECT COUNT(DISTINCT builder) FROM jobs WHERE stage='PRIVATE_QA_PASSED'"
        ).fetchone()[0]
        lesson_dir=root/"autonomous_education"
        lesson_count=(len(list(lesson_dir.glob("case-*.zip")))
                      if lesson_dir.is_dir() and not lesson_dir.is_symlink() else 0)
        return {"queues":dict(rows),"distinct_private_qa_artifact_versions":count,
                "self_directed_private_educational_editions":lesson_count,
                "self_directed_edition_interval_minutes":60,
                "self_directed_market_validation":False,
                "distinct_private_product_families":family_count,
                "available_specialist_builders":sorted(BUILDERS),
                "published_products":0,"verified_revenue":None,
                "autonomous_supply_from_real_sources_enabled":False}


def demo():
    """Self-contained sandbox demonstration, no persistent external effects."""
    with tempfile.TemporaryDirectory(prefix="astra-v2-private-demo-") as base:
        root=safe_root(Path(base)/"private")
        brief={
            "brief_id":"orchard_investment_audit_v1",
            "builder":BUILDER,"development_scope":"private_reference_prototype",
            "publication_allowed":False,"market_demand_verified":False,
            "paid_api_budget":0,
            "problem":"Review competing orchard investment cashflows under operator assumptions",
        }
        a=enqueue(root,brief)
        b=tick(root)
        c=tick(root)
        after=status(root)
        if not (a["new_job"] and b["status"]=="PRIVATE_QA_PASSED"
                and c["status"]=="NO_ELIGIBLE_WORK"
                and after["distinct_private_qa_artifact_versions"]==1):
            raise RuntimeError("END_TO_END_PRIVATE_DEMO_FAILED")
        return {"result":"PASSED","steps":["private_brief_registered",
                  "single_job_executed","technical_tests_passed",
                  "immutable_product_zip_and_qa_written",
                  "repeat_tick_skips_unchanged_work"],
                "new_distinct_private_versions":1,
                "commercial_products_released":0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("enqueue","tick","status","demo","loop"))
    parser.add_argument("--root",help="private workspace folder, never sites")
    parser.add_argument("--brief",help="local private brief JSON")
    parser.add_argument("--interval",type=int,default=300,
                        help="local heartbeat seconds, no API billing")
    args=parser.parse_args()
    if args.action=="demo":
        output=demo()
    else:
        if not args.root:parser.error("--root required")
        root=safe_root(args.root)
        if args.action=="enqueue":
            if not args.brief:parser.error("--brief required")
            src=Path(args.brief).expanduser()
            if src.is_symlink() or not src.is_file() or src.stat().st_size>20000:
                raise ValueError("unsafe product brief file")
            output=enqueue(root,json.loads(src.read_text(encoding="utf-8")))
        elif args.action=="tick":output=tick(root)
        elif args.action=="status":output=status(root)
        else:
            if not 60<=args.interval<=3600:parser.error("interval must be 60..3600s")
            while True:
                print(json.dumps(tick(root),sort_keys=True),flush=True)
                time.sleep(args.interval)
    print(json.dumps(output,sort_keys=True,ensure_ascii=False))


if __name__=="__main__":
    main()
