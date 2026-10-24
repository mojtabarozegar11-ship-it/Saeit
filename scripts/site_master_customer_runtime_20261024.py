#!/usr/bin/env python3
"""Tenant-isolated, API-free master inbox runner for site questions and orders.

The real deployed site master is invoked locally, then only trusted read-only
order/inquiry sources are projected into a private SQLite inbox. Never updates
an order, invoice, payment, web page, Django schema or another tenant.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
from urllib.parse import quote

HOME = Path("/home/zomorod2")
CONFIG = {
    "zomorod": {
        "root": HOME / ".private/zomorod-business",
        "source": HOME / ".private/zomorod-business/site_store.sqlite3",
        "master": HOME / ".private/zomorod-business/site_agents.php",
    },
    "mojplaywin": {
        "root": HOME / ".private_mojplaywin_main_agents",
        "django": HOME / "Saeit-staging",
        "master": HOME / ".private_mojplaywin_main_agents/v91_verified_main_port_20261018",
    },
}
API_WORDS = ("OPENAI", "ANTHROPIC", "GEMINI", "DEEPSEEK", "COHERE", "GROQ", "API_KEY")
MAX_BATCH = 30


def safe_root(site: str) -> Path:
    if site not in CONFIG:
        raise ValueError("UNKNOWN_SITE_TENANT")
    root = CONFIG[site]["root"]
    if not root.is_dir() or root.is_symlink() or root.stat().st_mode & 0o007:
        raise RuntimeError("PRIVATE_TENANT_STORAGE_UNSAFE")
    return root


def open_inbox(site: str) -> sqlite3.Connection:
    path = safe_root(site) / "master_customer_inbox.sqlite3"
    if not path.is_file() or path.is_symlink():
        raise RuntimeError("SITE_CUSTOMER_INBOX_NOT_INITIALIZED")
    if path.stat().st_mode & 0o077:
        raise RuntimeError("SITE_CUSTOMER_INBOX_NOT_PRIVATE")
    db = sqlite3.connect(str(path), timeout=8)
    db.execute("PRAGMA busy_timeout=8000")
    db.execute("PRAGMA foreign_keys=ON")
    required = {"customer_questions", "customer_order_events"}
    found = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not required.issubset(found):
        db.close()
        raise RuntimeError("SITE_CUSTOMER_INBOX_SCHEMA_INVALID")
    return db


def project_order(db: sqlite3.Connection, site: str, source: str, key: object, state: object) -> bool:
    if not re.fullmatch(r"[a-z_]{2,60}", source):
        raise ValueError("ORDER_SOURCE_UNRECOGNIZED")
    sid = str(key)
    status = str(state)
    if not re.fullmatch(r"[0-9]{1,17}", sid) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,45}", status):
        raise ValueError("ORDER_EVENT_UNSAFE")
    stamp = hashlib.sha256((site + "|" + source + "|" + sid + "|" + status).encode()).hexdigest()
    changed = db.execute(
        "INSERT OR IGNORE INTO customer_order_events(tenant,source,source_id,source_status,event_digest) VALUES (?,?,?,?,?)",
        (site, source, sid, status, stamp),
    ).rowcount
    return bool(changed)


def project_question(db: sqlite3.Connection, site: str, source: str, pk: int,
                     name: str, email: str, body: str) -> bool:
    if source not in ("company_inquiry", "authenticated_chat"):
        raise ValueError("QUESTION_SOURCE_UNRECOGNIZED")
    if not isinstance(pk, int) or pk <= 0 or pk > 10**14:
        raise ValueError("QUESTION_ID_INVALID")
    ticket = "native-" + source + "-" + str(pk)
    if not isinstance(body, str) or not body.strip():
        return False
    if len(body) > 2500:
        body = body[:2500]
    name = (name or "Customer")[:120]
    email = (email or "unknown@invalid.local")[:250]
    reply = ("پرسش دریافت شد؛ پاسخ اختصاصی نیازمند بررسی است." if site == "zomorod"
             else "Your question was received for verified site-master review.")
    return bool(db.execute(
        "INSERT OR IGNORE INTO customer_questions("
        "id,tenant,kind,full_name,email,question,claimed_order_ref,initial_reply,processing_status"
        ") VALUES(?,?,?,?,?,?,?,?,?)",
        (ticket, site, "question", name, email, body, "", reply, "queued"),
    ).rowcount)


def import_zomorod_order_ledger(db: sqlite3.Connection) -> dict:
    """Unknown ledgers fail closed. Never infer an order from a product listing."""
    source = CONFIG["zomorod"]["source"]
    if not source.is_file() or source.is_symlink():
        return {"source": "unavailable", "orders": 0}
    inserted = 0
    try:
        with sqlite3.connect("file:" + quote(str(source)) + "?mode=ro",
                             uri=True, timeout=7) as read:
            read.execute("PRAGMA query_only=ON")
            tables = {r[0] for r in read.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            candidates = ("orders", "customer_orders", "store_orders")
            present = [name for name in candidates if name in tables]
            for table in present:
                columns = {r[1] for r in read.execute('PRAGMA table_info("' + table + '")')}
                if not {"id", "status"}.issubset(columns):
                    continue
                for key, status in read.execute(
                    'SELECT id,status FROM "' + table + '" ORDER BY id DESC LIMIT 1000'
                ):
                    try:
                        inserted += int(project_order(db, "zomorod", table, key, status))
                    except ValueError:
                        continue
            return {"source": "local_store_ledger" if present else "no_orders_table",
                    "orders": inserted}
    except sqlite3.DatabaseError:
        return {"source": "unreadable", "orders": 0}


def import_mojplaywin_django(db: sqlite3.Connection) -> dict:
    app = CONFIG["mojplaywin"]["django"]
    if not (app / "manage.py").is_file() or app.is_symlink():
        raise RuntimeError("MPW_DJANGO_APP_IDENTITY_FAILED")
    if str(app) not in sys.path:
        sys.path.insert(0, str(app))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.apps import apps
    count = 0
    sources = (
        ("core.Order", "core_order"),
        ("mpw_commerce.CommerceInvoice", "commerce_invoice"),
        ("mpw_native_checkout.NativeInvoice", "native_invoice"),
    )
    for model_name, source_name in sources:
        try:
            model = apps.get_model(model_name)
            fields = {f.name for f in model._meta.fields}
            if "status" not in fields:
                continue
            for key, state in model.objects.order_by("-pk").values_list("pk", "status")[:1000]:
                try:
                    count += int(project_order(db, "mojplaywin", source_name, key, state))
                except ValueError:
                    pass
        except LookupError:
            continue
    inquiry_count = 0
    model = apps.get_model("core.CompanyInquiry")
    for pk, name, email, message in model.objects.order_by("-pk").values_list(
            "pk", "name", "email", "message")[:200]:
        inquiry_count += int(project_question(db, "mojplaywin", "company_inquiry", pk,
                                              name, email, message))
    chat = apps.get_model("core.ChatMessage")
    for pk, role, content in chat.objects.order_by("-pk").values_list(
            "pk", "role", "content")[:200]:
        if role == "user":
            inquiry_count += int(project_question(db, "mojplaywin", "authenticated_chat", pk,
                                                  "Authenticated customer", "unknown@invalid.local",
                                                  content))
    return {"source": "live_django_readonly", "orders": count, "questions": inquiry_count}


def master_callback(site: str, count: int) -> None:
    """Require an actual invocation of that site's existing master controller."""
    if site == "mojplaywin":
        root = CONFIG[site]["master"]
        if not root.is_dir() or root.is_symlink():
            raise RuntimeError("MPW_MASTER_NOT_AVAILABLE")
        os.environ.pop("DJANGO_SETTINGS_MODULE", None)
        for key in list(os.environ):
            if any(marker in key.upper() for marker in API_WORDS):
                os.environ.pop(key, None)
        sys.path.insert(0, str(root))
        from mpw_v91_port.worker import origin_ok
        if not origin_ok():
            raise RuntimeError("MPW_MASTER_SOURCE_FAILED_SHA")
        from mpw_v91_port.legacy.site_master.bridge import route_once
        result = route_once("mpw-inbox-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S"),
                            lambda: {"tenant": "mojplaywin-main", "status": "api_free_master_callback",
                                     "pending_items": count})
        if not isinstance(result, dict) or result.get("tenant") != "mojplaywin-main":
            raise RuntimeError("MPW_MASTER_CALLBACK_FAILED")
        return
    file = CONFIG[site]["master"]
    if not file.is_file() or file.is_symlink():
        raise RuntimeError("ZM_MASTER_NOT_AVAILABLE")
    # Invoke existing PHP master using in-memory DB and injected same-origin fixture:
    # never create synthetic success in the production run ledger.
    code = r'''
    require $argv[1];
    $d=new PDO("sqlite::memory:");
    $d->setAttribute(PDO::ATTR_ERRMODE,PDO::ERRMODE_EXCEPTION);
    $d->exec("CREATE TABLE agents(code TEXT,check_path TEXT,enabled INTEGER)");
    $d->exec("CREATE TABLE runs(id INTEGER PRIMARY KEY,agent_code TEXT,status TEXT,http_code INTEGER,duration_ms INTEGER,detail TEXT,occurred_at TEXT DEFAULT CURRENT_TIMESTAMP)");
    $d->exec("INSERT INTO agents VALUES ('master','/',1)");
    $r=zmAgentCycle($d,null,fn($url)=>['http'=>200,'bytes'=>200,'content_type'=>'text/html','error'=>'']);
    if(count($r)!==1 || $r[0][0]!=='master' || $r[0][1]!=='ok')exit(8);
    '''
    php = "/opt/cpanel/ea-php82/root/usr/bin/php"
    if not Path(php).is_file():
        php = "php"
    p = subprocess.run([php, "-d", "display_errors=0", "-r", code, str(file)],
                       capture_output=True, text=True, timeout=25, check=False)
    if p.returncode != 0:
        raise RuntimeError("ZM_LOCAL_MASTER_CALLBACK_FAILED")


# An acknowledgment is not a verified resolution. Financial and delivery
# cases always require review of the authoritative merchant ledger.
REQUIRES_VERIFICATION = re.compile(
    r"(refund|return|chargeback|payment|paid|invoice|receipt|order|purchase|"
    r"download|delivery|missing file|wallet|trx|transaction|"
    r"استرداد|مرجوع|بازگشت وجه|پرداخت|فاکتور|رسید|سفارش|خرید|دانلود|تحویل|فایل|کیف پول)",
    re.IGNORECASE,
)
PUBLIC_DISCOUNT_GUIDANCE = re.compile(r"(discount|coupon|promo code|تخفیف|کد تخفیف)", re.IGNORECASE)


def classify_customer_ticket(kind: str, question: str) -> str:
    """Conservatively route requests; never interpret a receipt as case closure."""
    if kind == "order_question" or REQUIRES_VERIFICATION.search(question):
        return "needs_review"
    # The public portal already gives verified *general* discount guidance:
    # price from product page; any actual discount needs management approval.
    if kind == "question" and PUBLIC_DISCOUNT_GUIDANCE.search(question):
        return "handled"
    return "needs_review"


def update_master_heartbeat(db: sqlite3.Connection, site: str) -> dict:
    """Private operational metrics only: no email, message, order ID or IP."""
    db.execute(
        "CREATE TABLE IF NOT EXISTS master_customer_worker_health("
        "tenant TEXT PRIMARY KEY, last_success_utc TEXT NOT NULL,"
        "queued INTEGER NOT NULL, review INTEGER NOT NULL, guidance INTEGER NOT NULL,"
        "review_older_than_day INTEGER NOT NULL)"
    )
    rows = db.execute(
        "SELECT processing_status,COUNT(*) FROM customer_questions WHERE tenant=? "
        "GROUP BY processing_status", (site,)
    ).fetchall()
    counts = {state: int(total) for state, total in rows}
    old = db.execute(
        "SELECT COUNT(*) FROM customer_questions WHERE tenant=? AND "
        "processing_status='needs_review' AND created_utc < datetime('now','-1 day')",
        (site,),
    ).fetchone()[0]
    metrics = {
        "queued": counts.get("queued", 0),
        "review": counts.get("needs_review", 0),
        "guidance": counts.get("handled", 0),
        "review_older_than_day": int(old),
    }
    db.execute(
        "INSERT INTO master_customer_worker_health "
        "(tenant,last_success_utc,queued,review,guidance,review_older_than_day)"
        "VALUES(?,CURRENT_TIMESTAMP,?,?,?,?) "
        "ON CONFLICT(tenant) DO UPDATE SET "
        "last_success_utc=CURRENT_TIMESTAMP,queued=excluded.queued,"
        "review=excluded.review,guidance=excluded.guidance,"
        "review_older_than_day=excluded.review_older_than_day",
        (site,metrics["queued"],metrics["review"],metrics["guidance"],
         metrics["review_older_than_day"]),
    )
    return metrics


def run(site: str) -> dict:
    os.umask(0o077)
    db = open_inbox(site)
    try:
        source = (import_mojplaywin_django(db) if site == "mojplaywin"
                  else import_zomorod_order_ledger(db))
        db.commit()
        pending = db.execute(
            "SELECT id,kind,question FROM customer_questions WHERE tenant=? AND processing_status='queued' "
            "ORDER BY created_utc,id LIMIT ?", (site, MAX_BATCH)).fetchall()
        master_callback(site, len(pending) + source["orders"])
        updated = 0
        for ticket, kind, question in pending:
            # Only deterministic advice was returned at intake. Specific order
            # status/payment questions remain for human verification.
            state = classify_customer_ticket(str(kind), str(question))
            updated += db.execute(
                "UPDATE customer_questions SET processing_status=?,master_processed_utc=CURRENT_TIMESTAMP "
                "WHERE id=? AND tenant=? AND processing_status='queued'",
                (state, ticket, site)).rowcount
        health = update_master_heartbeat(db,site)
        db.commit()
        return {"tenant": site, "mode": "local_no_external_ai_api",
                "real_site_master_invoked": True, "source": source,
                "questions_processed": updated, "questions_pending": health["queued"],
                "review_waiting": health["review"],
                "review_older_than_day": health["review_older_than_day"],
                "guidance_processed": health["guidance"],
                "payments_mutated": False, "external_messages_sent": False,
                "site_pages_mutated": False}
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True, choices=tuple(CONFIG))
    parser.add_argument("--once", action="store_true", required=True)
    args = parser.parse_args()
    result = run(args.site)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
