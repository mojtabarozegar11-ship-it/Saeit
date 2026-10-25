#!/usr/bin/env python3
"""Bounded, read-only MojPlayWin traffic and support-mailbox evidence.

Runs only on the established cPanel relay. NEVER prints IP addresses, emails,
message subjects/bodies, credentials, raw log lines, or ticket identifiers.
Traffic numbers are log-derived estimates, not GA4 sessions or human identities.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
import gzip
import json
import re
import subprocess

HOME = Path("/home/zomorod2")
DOMAIN = "mojplaywin.com"
NOW = datetime.now(timezone.utc)
CUTOFF = NOW - timedelta(days=30)
BOT = re.compile(r"bot|spider|crawl|monitor|uptime|headless|curl|wget|python-requests|postman|github-actions|go-http-client", re.I)
APACHE = re.compile(r'^(\S+)\s+\S+\s+\S+\s+\[([^\]]+)\]\s+"(GET|POST|HEAD)\s+(\S+)\s+HTTP/[^"]+"\s+(\d{3})\s+.*?"[^"]*"\s+"([^"]*)"')
ARCHIVE_NAME = re.compile(r"^(?:www\.)?mojplaywin\.com(?:[-_.].*)?(?:\.gz|\.log|_log)$", re.I)


def output(label, value):
    print(label + "=" + json.dumps(value, sort_keys=True, ensure_ascii=False))


def safe_directory(path):
    return path.is_dir() and not path.is_symlink()


def support_maildir():
    root = HOME / "mail" / DOMAIN / "support"
    report = {"source": "cpanel_maildir_metadata", "exists": safe_directory(root),
              "new": None, "cur": None, "unread_estimate": None,
              "messages_mtime_last_30d": None, "truncated": False}
    if not report["exists"]:
        output("MPW_SUPPORT_MAILBOX", report)
        return
    recent = 0
    unread = 0
    for folder in ("new", "cur"):
        base = root / folder
        if not safe_directory(base):
            continue
        count = 0
        for p in base.iterdir():
            if count >= 30000:
                report["truncated"] = True
                break
            if not p.is_file() or p.is_symlink():
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            count += 1
            if datetime.fromtimestamp(st.st_mtime, timezone.utc) >= CUTOFF:
                recent += 1
            if folder == "new" or (":2," in p.name and "S" not in p.name.rsplit(":2,", 1)[-1]):
                unread += 1
        report[folder] = count
    report["unread_estimate"] = unread
    report["messages_mtime_last_30d"] = recent
    output("MPW_SUPPORT_MAILBOX", report)




def configured_support_mailbox():
    info = {"source": "cpanel_Email_list_pops", "available": False,
            "support_account_present": None, "mail_forwarding_unknown": True}
    try:
        p = subprocess.run(
            ["uapi", "--output=json", "Email", "list_pops", "domain=" + DOMAIN],
            capture_output=True, timeout=18, check=False)
        if p.returncode == 0 and len(p.stdout) <= 3_000_000:
            obj = json.loads(p.stdout.decode("utf-8"))
            result = obj.get("result") or {}
            rows = result.get("data")
            if isinstance(rows, list) and result.get("status") in (1, True):
                info["available"] = True
                info["support_account_present"] = any(
                    str(row.get("email") or row.get("login") or row.get("user") or "").lower()
                    in ("support", "support@" + DOMAIN)
                    for row in rows if isinstance(row, dict))
    except (OSError, subprocess.TimeoutExpired, ValueError, UnicodeError, TypeError):
        pass
    output("MPW_SUPPORT_ACCOUNT", info)




def configured_support_forwarder():
    info = {"source": "cpanel_Email_list_forwarders", "available": False,
            "support_forwarder_present": None, "no_destinations_disclosed": True}
    try:
        p = subprocess.run(
            ["uapi", "--output=json", "Email", "list_forwarders", "domain=" + DOMAIN],
            capture_output=True, timeout=18, check=False)
        if p.returncode == 0 and len(p.stdout) <= 3_000_000:
            obj = json.loads(p.stdout.decode("utf-8"))
            result = obj.get("result") or {}
            rows = result.get("data")
            if isinstance(rows, list) and result.get("status") in (1, True):
                info["available"] = True
                info["support_forwarder_present"] = any(
                    str(row.get("email") or row.get("forward") or
                        row.get("from") or row.get("source") or "").lower()
                    in ("support", "support@" + DOMAIN)
                    for row in rows if isinstance(row, dict))
                info["forwarder_rows"] = len(rows)
                info["source_key_names"] = sorted(
                    set().union(*(row.keys() for row in rows if isinstance(row, dict))))[:20]
    except (OSError, subprocess.TimeoutExpired, ValueError, UnicodeError, TypeError):
        pass
    output("MPW_SUPPORT_FORWARDER", info)



def domain_catchall():
    info = {"source": "cpanel_Email_list_default_address",
            "available": False, "catchall_delivery": "unknown",
            "destinations_hidden": True}
    try:
        p = subprocess.run(
            ["uapi", "--output=json", "Email", "list_default_address",
             "domain=" + DOMAIN], capture_output=True, timeout=18, check=False)
        if p.returncode == 0 and len(p.stdout) <= 3_000_000:
            obj = json.loads(p.stdout.decode("utf-8"))
            result = obj.get("result") or {}
            data = result.get("data")
            if result.get("status") in (1, True):
                info["available"] = True
                info["data_type"] = type(data).__name__
                info["field_names"] = sorted(data.keys()) if isinstance(data, dict) else []
                if isinstance(data, list):
                    info["row_count"] = len(data)
                    info["field_names"] = sorted(set().union(*(r.keys() for r in data if isinstance(r, dict))))[:20]
                    scoped = [r for r in data if isinstance(r, dict)
                              and str(r.get("domain") or "").lower() == DOMAIN]
                    if scoped:
                        value = str(scoped[0].get("defaultaddress") or "").strip()
                        if value.startswith((":fail:", ":blackhole:")):
                            info["catchall_delivery"] = "rejected_or_discarded"
                        elif value and "@" in value:
                            info["catchall_delivery"] = "mailbox_or_forward_target_configured"
                        elif value:
                            info["catchall_delivery"] = "other_unverified_configuration"
                # Never publish routing destinations; classification is conservative.
                if isinstance(data, dict):
                    route = str(data.get("forward") or data.get("dest") or
                                data.get("address") or data.get("default") or "").strip()
                    if route.startswith((":fail:", ":blackhole:")):
                        info["catchall_delivery"] = "rejected_or_discarded"
                    elif route and "@" in route:
                        info["catchall_delivery"] = "address_configured_unverified"
    except (OSError, subprocess.TimeoutExpired, ValueError, UnicodeError, TypeError):
        pass
    output("MPW_DOMAIN_CATCHALL", info)

def route_bucket(page):
    if page.startswith(("/mpw-editorial/revenue/", "/earn/")):
        return "revenue_hub" if page in ("/mpw-editorial/revenue/", "/mpw-editorial/revenue/index.html", "/earn/", "/earn/index.html") else "revenue_offer"
    if page.startswith("/store/product/"):
        return "product_checkout" if "/checkout/" in page else "product_detail"
    if page.startswith("/store/") or page == "/store":
        return "store"
    if page.startswith("/commerce/trx-easy/"):
        return "trx_invoice" if "/invoice/" in page else "trx_other"
    if page.startswith("/accounts/"):
        return ("account_login" if "/login" in page else
                "account_register" if "/register" in page else "account_other")
    if page.startswith("/ask-master/"):
        return "support_ticket"
    if page.startswith(("/support/", "/contact/")):
        return "support_contact"
    if page.startswith(("/admin/", "/wp-admin/", "/.env", "/cgi-bin/")):
        return "scan_or_admin"
    if page == "/":
        return "home"
    for prefix in ("/games/", "/ai/", "/research/", "/knowledge/",
                   "/api/", "/topics/", "/blockchain/", "/services/"):
        if page.startswith(prefix):
            return prefix.strip("/")
    return "other"

def recent_cpanel_visitors():
    """Legacy cPanel API has no equivalent UAPI; do not echo its raw PII."""
    result = {"source": "cpanel_Stats_lastvisitors", "available": False,
              "sample_rows": None, "limited_recent_sample": True}
    try:
        p = subprocess.run(
            ["cpapi2", "--user=zomorod2", "Stats", "lastvisitors",
             "domain=" + DOMAIN], capture_output=True, timeout=18, check=False)
        if p.returncode == 0 and len(p.stdout) <= 5_000_000:
            obj = json.loads(p.stdout.decode("utf-8"))
            data = (obj.get("cpanelresult") or {}).get("data")
            if isinstance(data, list):
                result.update(available=True, sample_rows=len(data))
    except (OSError, subprocess.TimeoutExpired, ValueError, UnicodeError, TypeError):
        pass
    output("MPW_RECENT_VISITOR_SAMPLE", result)


def visitor_logs():
    # cPanel documents archived Raw Access logs in the account's logs directory.
    root = HOME / "logs"
    report = {"source": "cpanel_archived_raw_access", "available": False,
              "archive_count": 0, "truncated": False, "log_lines_scanned": 0,
              "within_30d": 0, "likely_human_page_hits": 0,
              "likely_bot_page_hits": 0, "approx_distinct_ips": 0,
              "store_page_hits": 0, "product_page_hits": 0,
              "checkout_page_hits": 0, "revenue_hub_hits": 0,
              "revenue_offer_hits": 0, "contact_page_hits": 0,
              "page_4xx": 0, "page_5xx": 0,
              "earliest_utc": None, "latest_utc": None,
              "limitations": "Raw archived logs may omit current days; IPs and user-agent heuristics are not people or sessions."}
    if not safe_directory(root):
        output("MPW_VISITOR_LOGS", report)
        return
    files = []
    for p in root.iterdir():
        if (p.is_symlink() or not p.is_file() or not ARCHIVE_NAME.fullmatch(p.name)
                or not p.name.lower().endswith(".gz")):
            continue
        if p.stat().st_size <= 80_000_000:
            files.append(p)
    files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:12]
    report["archive_count"] = len(files)
    if not files:
        output("MPW_VISITOR_LOGS", report)
        return
    report["available"] = True
    unique = set()
    errors_by_bucket = Counter()
    errors_by_day = Counter()
    login_errors_by_day = Counter()
    first = last = None
    for p in files:
        try:
            with gzip.open(p, "rt", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    report["log_lines_scanned"] += 1
                    if report["log_lines_scanned"] > 1_500_000:
                        report["truncated"] = True
                        break
                    m = APACHE.match(line)
                    if not m:
                        continue
                    ip, when, method, path, status, agent = m.groups()
                    try:
                        at = datetime.strptime(when, "%d/%b/%Y:%H:%M:%S %z").astimezone(timezone.utc)
                    except ValueError:
                        continue
                    if not (CUTOFF <= at <= NOW + timedelta(minutes=5)):
                        continue
                    report["within_30d"] += 1
                    first = min(first, at) if first else at
                    last = max(last, at) if last else at
                    page = path.split("?", 1)[0]
                    if method not in ("GET", "POST") or not (page.endswith("/") or page.endswith((".html", ".php"))):
                        continue
                    if BOT.search(agent):
                        report["likely_bot_page_hits"] += 1
                        continue
                    report["likely_human_page_hits"] += 1
                    if status.startswith(("4", "5")):
                        errors_by_bucket[route_bucket(page) + ":" + status] += 1
                        errors_by_day[at.date().isoformat() + ":" + status[0] + "xx"] += 1
                        if status == "403" and page.startswith("/accounts/"):
                            login_errors_by_day[at.date().isoformat() + ":" + route_bucket(page)] += 1
                    unique.add(ip)
                    bucket = route_bucket(page)
                    if bucket == "revenue_hub":
                        report["revenue_hub_hits"] += 1
                    elif bucket == "revenue_offer":
                        report["revenue_offer_hits"] += 1
                    elif bucket == "support_contact":
                        report["contact_page_hits"] += 1
                    if page.startswith("/store/") or page == "/store/":
                        report["store_page_hits"] += 1
                    if page.startswith("/store/product/") and not page.endswith("/checkout/"):
                        report["product_page_hits"] += 1
                    if page.endswith("/checkout/"):
                        report["checkout_page_hits"] += 1
                    if status.startswith("4"):
                        report["page_4xx"] += 1
                    if status.startswith("5"):
                        report["page_5xx"] += 1
        except (OSError, EOFError, ValueError):
            continue
        if report["truncated"]:
            break
    report["approx_distinct_ips"] = len(unique)
    report["earliest_utc"] = first.isoformat() if first else None
    report["latest_utc"] = last.isoformat() if last else None
    output("MPW_VISITOR_LOGS", report)
    output("MPW_ERROR_BUCKETS", {"source": "same_archived_access_logs",
                                "codes_by_route": dict(errors_by_bucket.most_common(30)),
                                "no_url_or_ip_disclosed": True})
    output("MPW_ERROR_DAYS", {"day_and_status_class": dict(sorted(errors_by_day.items())),
                              "source": "same_archived_access_logs"})
    output("MPW_ACCOUNT_403_DAYS", {"day_and_route": dict(sorted(login_errors_by_day.items())),
                                   "source": "same_archived_access_logs"})



def domain_mail_delivery_readiness():
    """Check mail-exchanger role and public DNS without mutating mail service."""
    report = {"source": "cpanel_Email_getmxcheck", "available": False,
              "routing_type": "unknown", "accepts_locally": None,
              "dns_mx": [], "dns_available": False, "readonly": True}
    try:
        p = subprocess.run(
            ["cpapi2", "--user=zomorod2", "--output=json", "Email",
             "getmxcheck", "domain=" + DOMAIN],
            capture_output=True, timeout=18, check=False)
        if p.returncode == 0 and len(p.stdout) < 100000:
            obj = json.loads(p.stdout.decode("utf-8"))
            rows = (obj.get("cpanelresult") or {}).get("data")
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    if str(row.get("domain") or DOMAIN).lower() != DOMAIN:
                        continue
                    kind = str(row.get("mxcheck") or "").lower()
                    if kind in ("auto", "local", "secondary", "remote"):
                        report["available"] = True
                        report["routing_type"] = kind
                    always = row.get("alwaysaccept")
                    if always in ("0", "1", 0, 1):
                        report["accepts_locally"] = str(always) == "1"
                    break
    except (OSError, subprocess.TimeoutExpired, ValueError, UnicodeError, TypeError):
        pass
    try:
        p = subprocess.run(["dig", "+short", "+time=3", "+tries=1",
                            "MX", DOMAIN], capture_output=True,
                           timeout=10, check=False)
        if p.returncode == 0 and len(p.stdout) < 8000:
            lines = p.stdout.decode("utf-8", "replace").splitlines()
            report["dns_available"] = True
            report["dns_mx"] = [
                " ".join(line.split()[:2])[:190]
                for line in lines[:12]
                if len(line.split()) == 2 and line.split()[0].isdigit()
            ]
    except (OSError, subprocess.TimeoutExpired, UnicodeError, TypeError):
        pass
    output("MPW_MAIL_ROUTING", report)


def email_dns_authentication():
    """Only report public DNS posture, never dump TXT records or DKIM keys."""
    names = ((DOMAIN, "spf"), ("default._domainkey." + DOMAIN, "dkim"),
             ("_dmarc." + DOMAIN, "dmarc"))
    findings = {"source": "public_dns_readonly", "readonly": True}
    for name, kind in names:
        found = False
        available = False
        policy = "unknown"
        try:
            p = subprocess.run(
                ["dig", "+short", "+time=3", "+tries=1", "TXT", name],
                capture_output=True, timeout=10, check=False)
            if p.returncode == 0 and len(p.stdout) < 16000:
                available = True
                txt = " ".join(p.stdout.decode("utf-8", "replace").splitlines())
                normalized = txt.replace('"', '').lower()
                if kind == "spf":
                    found = "v=spf1" in normalized
                elif kind == "dkim":
                    found = "v=dkim1" in normalized or "p=" in normalized
                else:
                    found = "v=dmarc1" in normalized
                    for option in ("reject", "quarantine", "none"):
                        if "p=" + option in normalized:
                            policy = option
                            break
        except (OSError, subprocess.TimeoutExpired, UnicodeError, TypeError):
            pass
        findings[kind + "_resolver_available"] = available
        findings[kind + "_record_present"] = found
        if kind == "dmarc":
            findings["dmarc_policy"] = policy
    output("MPW_EMAIL_AUTH_DNS", findings)

if __name__ == "__main__":
    support_maildir()
    configured_support_mailbox()
    configured_support_forwarder()
    domain_catchall()
    domain_mail_delivery_readiness()
    email_dns_authentication()
    recent_cpanel_visitors()
    visitor_logs()
    output("MPW_INTAKE_READONLY", {"result": "completed", "production_db_writes": False,
                                  "mail_content_read": False, "raw_identifiers_printed": False})
