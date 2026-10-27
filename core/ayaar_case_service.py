"""Private case storage and evidence workflow for AYAR.

No connection to MojPlayWin's application database or payment tables.
Only the Django AYAR API imports this module. Report grades are reviewer-
attested and are NEVER independent certifications by their mere existence.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import hmac
import json
import os
import pwd
import re
import secrets
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = "AYAR-CASE-v1"
MAX_FILE = 4 * 1024 * 1024
MAX_ATTACHMENTS = 3
MAX_REQUEST = 10 * 1024 * 1024
MAX_TOTAL_FILES = 250 * 1024 * 1024
MAX_CASES_PER_HOUR = 4
MAX_FOLLOWUPS = 8
MAX_FILES_PER_CASE = 12
MAX_BYTES_PER_CASE = 30 * 1024 * 1024
CASE_TYPES = {"ebook", "game", "software", "media"}
SERVICE_TYPES = {"screening", "professional", "enterprise"}
STATUSES = {"submitted", "in_review", "needs_information", "reviewed", "declined"}
RUBRICS = {
    "ebook": (("accuracy", 18, True), ("sources", 16, False),
              ("rights", 16, True), ("editing", 10, False),
              ("experience", 10, False), ("accessibility", 10, False),
              ("security", 8, True), ("delivery", 12, False)),
    "game": (("gameplay", 19, False), ("reliability", 17, False),
             ("security", 15, True), ("rights", 15, True),
             ("accessibility", 10, False), ("economy", 10, False),
             ("compatibility", 8, False), ("delivery", 6, False)),
    "software": (("functionality", 20, True), ("security", 20, True),
                 ("reliability", 15, False), ("privacy", 10, True),
                 ("rights", 10, True), ("documentation", 10, False),
                 ("accessibility", 8, False), ("deployment", 7, False)),
    "media": (("provenance", 15, False), ("creative", 15, False),
              ("rights", 20, True), ("technical", 15, False),
              ("accessibility", 10, False), ("packaging", 10, False),
              ("security", 5, True), ("utility", 10, False)),
}
for _row in RUBRICS.values():
    assert len(_row) == 8 and sum(weight for _, weight, _ in _row) == 100


class CaseError(ValueError):
    def __init__(self, reason: str, status: int = 400):
        super().__init__(reason)
        self.status = status


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def root() -> Path:
    """AYAR only, outside the web document root; override only for tests."""
    override = os.environ.get("AYAAR_CASE_TEST_DIR")
    target = Path(override) if override else Path(pwd.getpwuid(os.getuid()).pw_dir) / ".ayaar-private-cases-v1"
    if target.is_symlink():
        raise CaseError("Unsafe storage directory", 503)
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    if target.resolve() != target:
        raise CaseError("Unexpected storage path", 503)
    os.chmod(target, 0o700)
    return target


@contextlib.contextmanager
def database():
    path = root() / "ayaar.sqlite3"
    if path.is_symlink():
        raise CaseError("Unsafe database path", 503)
    connection = sqlite3.connect(str(path), timeout=8)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA busy_timeout=8000")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS cases(
              code TEXT PRIMARY KEY, secret_hash TEXT NOT NULL,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
              status TEXT NOT NULL, category TEXT NOT NULL, service TEXT NOT NULL,
              product_name TEXT NOT NULL, product_version TEXT NOT NULL,
              product_url TEXT NOT NULL, requester_email TEXT NOT NULL,
              scope TEXT NOT NULL, evidence_summary TEXT NOT NULL,
              rights_declared INTEGER NOT NULL, publication_consent INTEGER NOT NULL,
              review TEXT NOT NULL DEFAULT '', reviewer_username TEXT NOT NULL DEFAULT '',
              independence_statement TEXT NOT NULL DEFAULT '',
              public_report INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS events(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              code TEXT NOT NULL REFERENCES cases(code),
              occurred_at TEXT NOT NULL, actor TEXT NOT NULL,
              action TEXT NOT NULL, detail TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS files(
              id TEXT PRIMARY KEY, code TEXT NOT NULL REFERENCES cases(code),
              original_name TEXT NOT NULL, stored_name TEXT NOT NULL,
              size INTEGER NOT NULL, sha256 TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS intake_limiter(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              identity_hash TEXT NOT NULL, occurred_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_case_status ON cases(status,created_at);
            CREATE INDEX IF NOT EXISTS idx_file_case ON files(code);
            CREATE INDEX IF NOT EXISTS idx_rate ON intake_limiter(identity_hash,occurred_at);
        """)
        if path.exists():
            os.chmod(path, 0o600)
        yield connection
    finally:
        connection.close()


def clean(value, limit=1000, required=False):
    if not isinstance(value, str):
        raise CaseError("Invalid text value")
    cleaned = "".join(ch for ch in value.strip() if ch >= " " or ch in "\n\t")
    if len(cleaned) > limit or (required and len(cleaned) < 2):
        raise CaseError("Required text is missing or too long")
    return cleaned


def https_url(value):
    value = clean(value, 500)
    if not value:
        return ""
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise CaseError("Product reference must use a public HTTPS URL")
    if not parsed.hostname or parsed.hostname in ("localhost", "127.0.0.1", "::1") or parsed.hostname.endswith(".local"):
        raise CaseError("Private network references are not accepted")
    return value


def email_address(value):
    value = clean(value, 180)
    if value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise CaseError("Invalid contact email")
    return value


def source_identity(remote_addr, secret_key):
    # Do not store plaintext addresses; retain only short-lived keyed hash.
    address = remote_addr if isinstance(remote_addr, str) else ""
    return hmac.new(secret_key.encode(), address.encode(), hashlib.sha256).hexdigest()


def classify_file(upload):
    filename = clean(getattr(upload, "name", ""), 150, True)
    size = getattr(upload, "size", 0)
    if not isinstance(size, int) or size < 1 or size > MAX_FILE:
        raise CaseError("Evidence attachment exceeds its 4 MB limit")
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".png", ".jpg", ".jpeg", ".txt"}:
        raise CaseError("Only PDF, PNG, JPEG or plain text evidence is accepted")
    initial = upload.read(16)
    upload.seek(0)
    if suffix == ".pdf" and not initial.startswith(b"%PDF-"):
        raise CaseError("PDF signature mismatch")
    if suffix == ".png" and not initial.startswith(b"\x89PNG\r\n\x1a\n"):
        raise CaseError("PNG signature mismatch")
    if suffix in (".jpg", ".jpeg") and not initial.startswith(b"\xff\xd8\xff"):
        raise CaseError("JPEG signature mismatch")
    if suffix == ".txt" and b"\x00" in initial:
        raise CaseError("Text evidence must not contain binary data")
    return filename, size, suffix


def event(db, code, actor, action, detail):
    db.execute(
        "INSERT INTO events(code,occurred_at,actor,action,detail) VALUES(?,?,?,?,?)",
        (code, now(), actor, action, detail)
    )


def create_case(payload, uploads, remote_addr, secret_key):
    if not isinstance(payload, dict):
        raise CaseError("Invalid application")
    category = clean(payload.get("category", ""), 20)
    service = clean(payload.get("service", ""), 25)
    if category not in CASE_TYPES or service not in SERVICE_TYPES:
        raise CaseError("Select a supported product and service")
    if payload.get("rights_declared") is not True or payload.get("privacy_consent") is not True:
        raise CaseError("Ownership and privacy acknowledgments are required")
    if payload.get("ai_processing_consent") is not True:
        raise CaseError("Explicit consent to AI-assisted review is required")
    name = clean(payload.get("product_name", ""), 120, True)
    version = clean(payload.get("product_version", ""), 80)
    product_url = https_url(payload.get("product_url", ""))
    email = email_address(payload.get("email", ""))
    scope = clean(payload.get("scope", ""), 2500, True)
    evidence = clean(payload.get("evidence_summary", ""), 2500)
    if not product_url and not evidence and not uploads:
        raise CaseError("Provide a secure product link or supporting evidence")
    if len(uploads) > MAX_ATTACHMENTS:
        raise CaseError("Maximum three evidence attachments")
    checks = [classify_file(item) for item in uploads]
    if sum(size for _, size, _ in checks) > MAX_REQUEST:
        raise CaseError("Total upload limit exceeded")
    record_time = now()
    code = "AYR-" + dt.datetime.now(dt.timezone.utc).strftime("%y") + "-" + secrets.token_hex(6).upper()
    access_key = secrets.token_urlsafe(32)
    secret_hash = hmac.new(secret_key.encode(), access_key.encode(), hashlib.sha256).hexdigest()
    files_dir = root() / "evidence"
    if files_dir.is_symlink():
        raise CaseError("Unsafe evidence directory", 503)
    files_dir.mkdir(mode=0o700, exist_ok=True)
    os.chmod(files_dir, 0o700)
    saved = []
    try:
        with database() as db, db:
            fingerprint = source_identity(remote_addr, secret_key)
            since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).isoformat(timespec="seconds")
            db.execute("DELETE FROM intake_limiter WHERE occurred_at < ?", (since,))
            attempted = db.execute(
                "SELECT count(*) FROM intake_limiter WHERE identity_hash=? AND occurred_at>=?",
                (fingerprint, since)
            ).fetchone()[0]
            if attempted >= MAX_CASES_PER_HOUR:
                raise CaseError("Submission limit reached. Please try again later.", 429)
            used = db.execute("SELECT COALESCE(SUM(size),0) FROM files").fetchone()[0]
            if used + sum(s for _, s, _ in checks) > MAX_TOTAL_FILES:
                raise CaseError("Evidence storage is currently at capacity", 503)
            db.execute(
                """INSERT INTO cases(code,secret_hash,created_at,updated_at,status,category,service,
                  product_name,product_version,product_url,requester_email,scope,evidence_summary,
                  rights_declared,publication_consent) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (code, secret_hash, record_time, record_time, "submitted", category, service,
                 name, version, product_url, email, scope, evidence, 1,
                 int(payload.get("publication_consent") is True))
            )
            for upload, (filename, size, suffix) in zip(uploads, checks):
                file_id = secrets.token_hex(12)
                stored = file_id + suffix
                destination = files_dir / stored
                saved.append(destination)
                with destination.open("xb") as stream:
                    os.chmod(destination, 0o600)
                    digest = hashlib.sha256()
                    counted = 0
                    for block in upload.chunks(chunk_size=65536):
                        counted += len(block)
                        if counted > MAX_FILE:
                            raise CaseError("Oversized upload")
                        digest.update(block)
                        stream.write(block)
                if counted != size:
                    raise CaseError("Upload length mismatch")
                db.execute(
                    "INSERT INTO files(id,code,original_name,stored_name,size,sha256) VALUES(?,?,?,?,?,?)",
                    (file_id, code, filename, stored, size, digest.hexdigest())
                )
            db.execute("INSERT INTO intake_limiter(identity_hash,occurred_at) VALUES(?,?)", (fingerprint, record_time))
            event(db, code, "customer", "submitted", "Evidence dossier received; assessment not yet performed")
            event(db, code, "customer", "ai_processing_consent",
                  "Applicant authorized AI-assisted analysis of case information")
    except BaseException:
        for item in saved:
            try:
                item.unlink()
            except OSError:
                pass
        raise
    return {
        "case_id": code, "access_key": access_key, "status": "submitted",
        "created_at": record_time, "message": "Dossier received; no independent review has occurred"
    }


def as_case(db, code, include_private=False):
    row = db.execute("SELECT * FROM cases WHERE code=?", (code,)).fetchone()
    if row is None:
        raise CaseError("Case not found", 404)
    values = {
        "case_id": row["code"], "created_at": row["created_at"],
        "updated_at": row["updated_at"], "status": row["status"],
        "category": row["category"], "service": row["service"],
        "product_name": row["product_name"], "product_version": row["product_version"],
        "product_url": row["product_url"], "scope": row["scope"],
        "evidence_summary": row["evidence_summary"],
        "ai_processing_consent": bool(db.execute(
            "SELECT 1 FROM events WHERE code=? AND action='ai_processing_consent' LIMIT 1", (code,)
        ).fetchone()),
        "events": [dict(e) for e in db.execute(
            "SELECT occurred_at,actor,action,detail FROM events WHERE code=? ORDER BY id", (code,)
        )],
        "files": [dict(f) for f in db.execute(
            "SELECT id,original_name,size,sha256 FROM files WHERE code=? ORDER BY id", (code,)
        )],
    }
    if row["review"]:
        values["review"] = json.loads(row["review"])
    if include_private:
        values.update({
            "contact_email": row["requester_email"],
            "publication_consent": bool(row["publication_consent"]),
            "reviewer_username": row["reviewer_username"],
            "independence_statement": row["independence_statement"],
            "public_report": bool(row["public_report"])
        })
    return values


def case_status(code, access_key, secret_key):
    code = clean(code, 28, True)
    access_key = clean(access_key, 100, True)
    with database() as db:
        row = db.execute("SELECT secret_hash FROM cases WHERE code=?", (code,)).fetchone()
        digest = hmac.new(secret_key.encode(), access_key.encode(), hashlib.sha256).hexdigest()
        if row is None or not hmac.compare_digest(digest, row["secret_hash"]):
            raise CaseError("Invalid case reference or access key", 403)
        result = as_case(db, code)
        if result.get("review"):
            integrity = result["review"].get("integrity")
            result["review_integrity_valid"] = (
                checked_report_proof(db.execute("SELECT * FROM cases WHERE code=?", (code,)).fetchone(),
                                     result["review"], secret_key) is not None
                if integrity else None
            )
        return result


def grant_ai_consent(code, access_key, secret_key):
    """Authenticated, explicit consent for pre-existing applicant dossiers."""
    code = clean(code, 28, True)
    access_key = clean(access_key, 100, True)
    with database() as db, db:
        row = db.execute("SELECT secret_hash,status FROM cases WHERE code=?", (code,)).fetchone()
        digest = hmac.new(secret_key.encode(), access_key.encode(), hashlib.sha256).hexdigest()
        if row is None or not hmac.compare_digest(digest, row["secret_hash"]):
            raise CaseError("Invalid case reference or access key", 403)
        if row["status"] in {"reviewed", "declined"}:
            raise CaseError("Consent cannot alter a completed dossier", 409)
        existing = db.execute(
            "SELECT 1 FROM events WHERE code=? AND action='ai_processing_consent' LIMIT 1",
            (code,)
        ).fetchone()
        if not existing:
            event(db, code, "customer", "ai_processing_consent",
                  "Applicant explicitly authorized AI-assisted analysis of this dossier")
    return {"case_id": code, "ai_processing_consent": True}


def append_case_evidence(code, access_key, note, uploads, secret_key):
    """Authenticated applicant reply to a *staff-requested* evidence question.

    Preserves the original case and all previous events; does not overwrite any
    reviewer statement or accept follow-ups to finalized/declined cases.
    """
    code = clean(code, 28, True)
    access_key = clean(access_key, 100, True)
    note = clean(note, 2000, True)
    if len(note) < 12:
        raise CaseError("Explain your follow-up in at least twelve characters")
    if len(uploads) > MAX_ATTACHMENTS:
        raise CaseError("Maximum three additional evidence attachments")
    checks = [classify_file(item) for item in uploads]
    new_bytes = sum(size for _, size, _ in checks)
    if new_bytes > MAX_REQUEST:
        raise CaseError("Total upload limit exceeded")
    files_dir = root() / "evidence"
    if not files_dir.is_dir() or files_dir.is_symlink():
        raise CaseError("Private evidence workspace is unavailable", 503)
    saved = []
    try:
        with database() as db, db:
            row = db.execute(
                "SELECT secret_hash,status FROM cases WHERE code=?", (code,)
            ).fetchone()
            digest = hmac.new(secret_key.encode(), access_key.encode(), hashlib.sha256).hexdigest()
            if row is None or not hmac.compare_digest(digest, row["secret_hash"]):
                raise CaseError("Invalid case reference or access key", 403)
            if row["status"] != "needs_information":
                raise CaseError("Follow-ups are accepted only after an information request", 409)
            count = db.execute(
                "SELECT COUNT(*) FROM events WHERE code=? AND action='customer_followup'", (code,)
            ).fetchone()[0]
            if count >= MAX_FOLLOWUPS:
                raise CaseError("Follow-up limit reached; contact the review team", 429)
            current_files, current_bytes = db.execute(
                "SELECT COUNT(*),COALESCE(SUM(size),0) FROM files WHERE code=?", (code,)
            ).fetchone()
            used = db.execute("SELECT COALESCE(SUM(size),0) FROM files").fetchone()[0]
            if current_files + len(checks) > MAX_FILES_PER_CASE or current_bytes + new_bytes > MAX_BYTES_PER_CASE:
                raise CaseError("This dossier has reached its evidence quota", 413)
            if used + new_bytes > MAX_TOTAL_FILES:
                raise CaseError("Evidence storage is currently at capacity", 503)
            for upload, (filename, size, suffix) in zip(uploads, checks):
                file_id = secrets.token_hex(12)
                stored = file_id + suffix
                destination = files_dir / stored
                saved.append(destination)
                with destination.open("xb") as stream:
                    os.chmod(destination, 0o600)
                    content_hash = hashlib.sha256()
                    total = 0
                    for block in upload.chunks(chunk_size=65536):
                        total += len(block)
                        if total > MAX_FILE:
                            raise CaseError("Oversized upload")
                        stream.write(block)
                        content_hash.update(block)
                if total != size:
                    raise CaseError("Upload length mismatch")
                db.execute(
                    "INSERT INTO files(id,code,original_name,stored_name,size,sha256) VALUES(?,?,?,?,?,?)",
                    (file_id, code, filename, stored, size, content_hash.hexdigest())
                )
            changed = db.execute(
                "UPDATE cases SET status='submitted',updated_at=? "
                "WHERE code=? AND status='needs_information'", (now(), code)
            )
            if changed.rowcount != 1:
                raise CaseError("This information request is no longer open", 409)
            event(db, code, "customer", "customer_followup", note)
    except BaseException:
        for item in saved:
            try:
                item.unlink()
            except OSError:
                pass
        raise
    return {"case_id": code, "status": "submitted", "attachments_added": len(checks),
            "message": "Response recorded and returned to the review queue"}


def delete_case(code, access_key, secret_key):
    """Owner-authorized erasure of the exact case and its evidence files."""
    code = clean(code, 28, True)
    access_key = clean(access_key, 100, True)
    with database() as db, db:
        row = db.execute("SELECT secret_hash FROM cases WHERE code=?", (code,)).fetchone()
        digest = hmac.new(secret_key.encode(), access_key.encode(), hashlib.sha256).hexdigest()
        if row is None or not hmac.compare_digest(digest, row["secret_hash"]):
            raise CaseError("Invalid case reference or access key", 403)
        stored = [item["stored_name"] for item in db.execute("SELECT stored_name FROM files WHERE code=?", (code,))]
        for name in stored:
            evidence = root() / "evidence" / name
            if evidence.is_symlink():
                raise CaseError("Unsafe evidence file; erasure requires operator intervention", 503)
        db.execute("DELETE FROM events WHERE code=?", (code,))
        db.execute("DELETE FROM files WHERE code=?", (code,))
        db.execute("DELETE FROM cases WHERE code=?", (code,))
    for name in stored:
        file_path = root() / "evidence" / name
        if file_path.is_file():
            file_path.unlink()
    return {"case_id": code, "deleted": True}


def staff_list(limit=40):
    with database() as db:
        rows = db.execute(
            """SELECT code AS case_id,created_at,updated_at,status,category,service,product_name,
              (SELECT count(*) FROM files WHERE files.code=cases.code) AS file_count
              FROM cases ORDER BY created_at DESC LIMIT ?""",
            (min(100, max(1, int(limit))),)
        ).fetchall()
        return [dict(row) for row in rows]


def staff_case(code):
    with database() as db:
        return as_case(db, clean(code, 28, True), include_private=True)


def set_status(code, status, actor, note):
    """Enforce the human-review lifecycle without bypassing open evidence requests."""
    code = clean(code, 28, True)
    if status not in {"in_review", "needs_information", "declined"}:
        raise CaseError("Unsupported staff transition")
    note = clean(note, 1000, True)
    if status in {"needs_information", "declined"} and len(note) < 12:
        raise CaseError("Give a clear evidence-based reason (at least twelve characters)")
    allowed = {
        "submitted": {"in_review", "needs_information", "declined"},
        "in_review": {"needs_information", "declined"},
        "needs_information": {"declined"},
        "reviewed": set(),
        "declined": set(),
    }
    with database() as db, db:
        row = db.execute("SELECT status FROM cases WHERE code=?", (code,)).fetchone()
        if row is None:
            raise CaseError("Case not found", 404)
        previous = row["status"]
        if status not in allowed.get(previous, set()):
            raise CaseError("Invalid case transition; resolve open requests before continuing", 409)
        changed = db.execute(
            "UPDATE cases SET status=?,updated_at=? WHERE code=? AND status=?",
            (status, now(), code, previous)
        )
        if changed.rowcount != 1:
            raise CaseError("Case changed while you were reviewing it; reload first", 409)
        event(db, code, actor, status, note)
    return {"case_id": code, "status": status}


def validate_review(category, criteria):
    if not isinstance(criteria, dict) or set(criteria) != {item[0] for item in RUBRICS[category]}:
        raise CaseError("All eight applicable review criteria are required")
    result = []
    score = 0
    blockers = []
    for identifier, weight, gate in RUBRICS[category]:
        item = criteria[identifier]
        if not isinstance(item, dict) or type(item.get("score")) is not int or not 0 <= item["score"] <= 5:
            raise CaseError("Scores must be integers between zero and five")
        evidence = clean(item.get("evidence", ""), 1000)
        if len(evidence) < 12:
            raise CaseError("Provide a substantial evidence note for every score")
        score += item["score"] / 5 * weight
        result.append({"criterion": identifier, "weight": weight, "score": item["score"],
                       "evidence": evidence, "critical": gate})
        if gate and item["score"] < 3:
            blockers.append(identifier)
    return result, round(score, 1), blockers


def report_proof(row, report, secret_key):
    """Keyed, domain-separated integrity code for one versioned AYAR assessment.

    This proves consistency with the AYAR server's signing key, not external
    reviewer independence, product quality or regulatory accreditation.
    """
    unsigned = {key: value for key, value in report.items() if key != "integrity"}
    statement = {
        "case_id": row["code"], "created_at": row["created_at"],
        "product_name": row["product_name"], "product_version": row["product_version"],
        "category": row["category"], "review": unsigned,
    }
    raw = json.dumps(statement, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":")).encode("utf-8")
    return hmac.new(secret_key.encode("utf-8"),
                    b"AYAR-REPORT-INTEGRITY-V1\x00" + raw, hashlib.sha256).hexdigest()


def checked_report_proof(row, report, secret_key):
    if not isinstance(report, dict):
        return None
    marker = report.get("integrity")
    if not isinstance(marker, dict) or marker.get("scheme") != "AYAR-HMAC-SHA256-v1":
        return None
    recorded = marker.get("proof")
    if not isinstance(recorded, str) or not re.fullmatch(r"[0-9a-f]{64}", recorded):
        return None
    expected = report_proof(row, report, secret_key)
    return recorded if hmac.compare_digest(recorded, expected) else None


def submit_review(code, actor, payload, secret_key):
    """Staff attestation, not a representation of independent accreditation."""
    if not isinstance(payload, dict):
        raise CaseError("Invalid review")
    independence = clean(payload.get("independence_statement", ""), 1500, True)
    scope = clean(payload.get("review_scope", ""), 1500, True)
    methodology_notes = clean(payload.get("methodology_notes", ""), 2000, True)
    if payload.get("review_mode") != "ai_assisted":
        raise CaseError("AYAR Expert Engine requires a documented AI-assisted review")
    source = clean(payload.get("ai_review_reference", ""), 300, True)
    if len(source) < 12:
        raise CaseError("Record a traceable AI review session reference")
    if payload.get("evidence_examined") is not True:
        raise CaseError("Confirm the available evidence was actually examined")
    if payload.get("no_material_conflict") is not True:
        raise CaseError("Disclose and acknowledge all material affiliations and limits")
    with database() as db, db:
        row = db.execute("SELECT * FROM cases WHERE code=?", (code,)).fetchone()
        if row is None:
            raise CaseError("Case not found", 404)
        if row["status"] == "reviewed":
            raise CaseError("Final reports cannot be silently overwritten")
        if row["status"] == "declined":
            raise CaseError("Declined cases cannot be finalized")
        if row["status"] != "in_review":
            raise CaseError("Start formal review and resolve outstanding evidence requests first", 409)
        consent = db.execute(
            "SELECT 1 FROM events WHERE code=? AND action='ai_processing_consent' LIMIT 1",
            (code,)
        ).fetchone()
        if not consent:
            raise CaseError("The applicant has not authorized AI-assisted review", 403)
        criteria, score, blockers = validate_review(row["category"], payload.get("criteria"))
        grade = ("Critical gate failure" if blockers else "Excellent" if score >= 90
                 else "Strong" if score >= 80 else "Acceptable with corrections" if score >= 70
                 else "Further review required")
        verdict = {
            "schema": "AYAR-AI-ASSISTED-REVIEW-v1",
            "report_kind": "AYAR Expert Engine analytical assessment",
            "reviewer_alias": "AYAR Expert Engine", "review_mode": "ai_assisted",
            "notice": "AI-assisted assessment, NOT independent human review or official certification",
            "reviewed_at": now(), "reviewer_account": actor,
            "ai_review_reference": source,
            "independence_statement": independence, "review_scope": scope,
            "methodology_notes": methodology_notes, "grade": grade,
            "score": score, "blocking_criteria": blockers, "criteria": criteria,
            "final_disclaimer": "This AI-assisted internal assessment may be incomplete or mistaken and does not establish independent third-party accreditation."
        }
        verdict["integrity"] = {
            "scheme": "AYAR-HMAC-SHA256-v1",
            "proof": report_proof(row, verdict, secret_key),
            "notice": "AYAR server record integrity only; NOT independent accreditation"
        }
        public = int(row["publication_consent"] and payload.get("publish_report") is True)
        changed = db.execute(
            """UPDATE cases SET status='reviewed',updated_at=?,review=?,reviewer_username=?,
              independence_statement=?,public_report=? WHERE code=? AND status='in_review'""",
            (now(), json.dumps(verdict, ensure_ascii=False), actor, independence, public, code)
        )
        if changed.rowcount != 1:
            raise CaseError("Case changed while you were reviewing it; reload first", 409)
        event(db, code, actor, "reviewed", "Staff recorded documented AYAR Expert Engine analysis")
        return {"case_id": code, "status": "reviewed", "score": score,
                "grade": grade, "public_report": bool(public)}


def registry(secret_key):
    with database() as db:
        rows = db.execute(
            """SELECT code,created_at,updated_at,category,product_name,product_version,review
               FROM cases WHERE status='reviewed' AND public_report=1
               ORDER BY updated_at DESC LIMIT 100"""
        ).fetchall()
        results = []
        for row in rows:
            report = json.loads(row["review"])
            proof = checked_report_proof(row, report, secret_key)
            if report.get("integrity") and proof is None:
                # Fail closed on a changed or malformed signed report.
                continue
            results.append({
                "case_id": row["code"], "product_name": row["product_name"],
                "product_version": row["product_version"], "category": row["category"],
                "reviewed_at": row["updated_at"], "grade": report["grade"],
                "score": report["score"], "notice": report["notice"],
                "proof": proof or "", "integrity_status": "signed" if proof else "legacy"
            })
        return results



def verify_public_report(code, supplied_proof, secret_key):
    """Verify only customer-authorized published records, never private cases."""
    negative = {"verified": False, "notice": "No matching published AYAR integrity record"}
    if not isinstance(code, str) or not isinstance(supplied_proof, str):
        return negative
    if not re.fullmatch(r"AYR-[0-9]{2}-[0-9A-F]{12}", code.strip()):
        return negative
    if not re.fullmatch(r"[0-9a-f]{64}", supplied_proof.strip()):
        return negative
    with database() as db:
        row = db.execute(
            """SELECT * FROM cases
               WHERE code=? AND status='reviewed' AND public_report=1""",
            (code.strip(),)
        ).fetchone()
        if row is None or not row["review"]:
            return negative
        report = json.loads(row["review"])
        stored = checked_report_proof(row, report, secret_key)
        if not stored or not hmac.compare_digest(stored, supplied_proof.strip()):
            return negative
        return {
            "verified": True, "case_id": row["code"],
            "product_name": row["product_name"],
            "product_version": row["product_version"],
            "category": row["category"], "reviewed_at": report["reviewed_at"],
            "grade": report["grade"], "score": report["score"],
            "integrity_scheme": "AYAR-HMAC-SHA256-v1",
            "notice": "AYAR-issued record consistency only; NOT proof of independent reviewer credentials, external certification or product quality."
        }


def staff_file(code, file_id):
    with database() as db:
        row = db.execute(
            "SELECT original_name,stored_name,size,sha256 FROM files WHERE code=? AND id=?",
            (clean(code, 28, True), clean(file_id, 30, True))
        ).fetchone()
        if row is None:
            raise CaseError("Evidence file not found", 404)
        path = root() / "evidence" / row["stored_name"]
        if not path.is_file() or path.is_symlink():
            raise CaseError("Evidence file unavailable", 404)
        return path, row["original_name"]
