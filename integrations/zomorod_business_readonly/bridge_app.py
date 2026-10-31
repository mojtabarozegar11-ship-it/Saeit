"""Offline-only candidate: isolated read-only WSGI bridge for Zomorod business.

NOT mounted or deployed. Keep all credentials outside GitHub.
"""
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import parse_qs


BASE_HEADERS = [
    ("Content-Type", "application/json; charset=utf-8"),
    ("Cache-Control", "no-store, max-age=0"),
    ("X-Content-Type-Options", "nosniff"),
    ("X-Robots-Tag", "noindex, nofollow"),
    ("Referrer-Policy", "no-referrer"),
]


def create_app(config=None):
    config = dict(os.environ if config is None else config)
    stored_hash = config.get("ZM_RO_BRIDGE_TOKEN_SHA256", "")
    db_name = config.get("ZM_RO_BRIDGE_DB", "")
    root = config.get("DOCUMENT_ROOT", "")
    try:
        networks = [ipaddress.ip_network(part.strip(), strict=False)
                    for part in config.get("ZM_RO_BRIDGE_ALLOWED_IPS", "").split(",")
                    if part.strip()]
    except ValueError:
        networks = []
    db_path = Path(db_name) if db_name else None
    root_path = Path(root) if root else None
    # The document root is mandatory: omitting it must never disable the
    # private-DB containment check. Only explicitly approved single IPs
    # may reach financial and project records.
    ready = bool(
        networks and all(net.prefixlen == net.max_prefixlen for net in networks)
        and db_path is not None and db_path.is_absolute()
        and root_path is not None and root_path.is_absolute()
        and db_path.name == "management.sqlite3"
        and re.fullmatch("[0-9a-fA-F]{64}", stored_hash)
    )
    if ready:
        try:
            # Do not follow symlinks for either security boundary.
            if (db_path.is_symlink() or root_path.is_symlink()
                    or db_path.resolve().is_relative_to(root_path.resolve())):
                ready = False
        except (OSError, RuntimeError):
            ready = False

    def output(start, status, body):
        data = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
        start(status, BASE_HEADERS + [("Content-Length", str(len(data)))])
        return [data]

    def app(env, start):
        if not ready or env.get("wsgi.url_scheme") != "https":
            return output(start, "404 Not Found", {"error": "unavailable"})
        try:
            remote = ipaddress.ip_address(env.get("REMOTE_ADDR", ""))
        except ValueError:
            return output(start, "403 Forbidden", {"error": "denied"})
        # Never infer client IP from an unaudited X-Forwarded-For header.
        if not any(remote in network for network in networks):
            return output(start, "403 Forbidden", {"error": "denied"})
        if env.get("REQUEST_METHOD") != "GET":
            return output(start, "405 Method Not Allowed", {"error": "read_only"})
        authorization = env.get("HTTP_AUTHORIZATION", "").split(" ")
        if len(authorization) != 2 or authorization[0] != "Bearer" or not 32 <= len(authorization[1]) <= 256:
            return output(start, "401 Unauthorized", {"error": "unauthorized"})
        proposed = hashlib.sha256(authorization[1].encode()).hexdigest()
        if not hmac.compare_digest(proposed.lower(), stored_hash.lower()):
            return output(start, "401 Unauthorized", {"error": "unauthorized"})
        route = env.get("PATH_INFO", "")
        if route not in ("/v1/health", "/v1/projects", "/v1/finance-summary", "/v1/inventory"):
            return output(start, "404 Not Found", {"error": "not_found"})
        params = parse_qs(env.get("QUERY_STRING", ""), keep_blank_values=True)
        values = params.get("limit", ["50"])
        if (len(values) != 1 or not re.fullmatch("[1-9][0-9]{0,2}", values[0])
                or int(values[0]) > 100 or set(params) - {"limit"}):
            return output(start, "400 Bad Request", {"error": "invalid_query"})
        limit = int(values[0])
        try:
            if not db_path.is_file():
                return output(start, "503 Service Unavailable", {"error": "source_unavailable"})
            with sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.8) as db:
                db.execute("PRAGMA query_only=ON")
                db.execute("PRAGMA busy_timeout=500")
                db.row_factory = sqlite3.Row
                if route == "/v1/health":
                    db.execute("SELECT 1").fetchone()
                    answer = {"status": "ok", "access": "read_only"}
                elif route == "/v1/projects":
                    rows = db.execute(
                        "SELECT id,title,owner,state,budget FROM projects ORDER BY id LIMIT ?",
                        (limit,)).fetchall()
                    answer = {"projects": [dict(r) for r in rows], "limit": limit}
                elif route == "/v1/finance-summary":
                    rows = db.execute(
                        """SELECT i.currency, i.kind, COUNT(*) invoice_count,
                           SUM(i.amount) amount_stored_integer,
                           SUM(COALESCE(p.paid,0)) paid_stored_integer,
                           SUM(i.amount-COALESCE(p.paid,0)) unpaid_stored_integer,
                           SUM(CASE WHEN i.due_date<date('now') AND
                             i.amount>COALESCE(p.paid,0)
                             THEN i.amount-COALESCE(p.paid,0) ELSE 0 END)
                             overdue_stored_integer
                           FROM invoices i LEFT JOIN
                           (SELECT invoice_id,SUM(amount) paid
                            FROM invoice_payments GROUP BY invoice_id) p
                           ON p.invoice_id=i.id
                           GROUP BY i.currency,i.kind ORDER BY i.currency,i.kind"""
                    ).fetchall()
                    answer = {"by_currency_and_kind": [dict(r) for r in rows],
                              "note": "Stored integers, no profit or FX conversion."}
                else:
                    rows = db.execute(
                        """SELECT i.id,i.sku,i.name,i.unit,i.reorder_level,
                           COALESCE(SUM(m.qty),0) on_hand
                           FROM inventory i LEFT JOIN inventory_movements m
                           ON m.inventory_id=i.id
                           GROUP BY i.id ORDER BY i.id LIMIT ?""",
                        (limit,)).fetchall()
                    answer = {"inventory": [dict(r) for r in rows], "limit": limit}
            return output(start, "200 OK", answer)
        except (sqlite3.Error, OSError, ValueError):
            return output(start, "503 Service Unavailable", {"error": "source_unavailable"})

    return app


# Intentionally no global live WSGI application.
