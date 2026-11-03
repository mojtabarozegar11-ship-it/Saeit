#!/usr/bin/env python3
"""Fail-closed, additive-only private ZM V7 reconciler.

This script must execute on the owner-controlled host. It never prints or exports
live source, never writes the effective app.php, and never opens the ledger for
writing. Its staged result is NOT a release authorization.
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import sqlite3
import sys


class Blocked(Exception):
    pass


ROUTES = (
    "insights", "command_center", "workflow_desk", "industry_ops",
    "period_controls", "finance_audit", "payroll",
)
ACTIONS = (
    "cc_create", "cc_scan", "cc_transition", "cc_plan", "cc_evidence",
    "cc_review", "flow_create", "flow_transition", "industry_create",
    "industry_advance", "period_freeze", "period_close",
    "payroll_create", "payroll_decision",
)
ADDED = (
    "journal_reverse", "user_update", "approval_register", "chatgpt_reports",
)


def exactly_one(haystack: str, needle: str, label: str) -> int:
    count = haystack.count(needle)
    if count != 1:
        raise Blocked(f"ANCHOR_{label}_COUNT_{count}")
    return haystack.index(needle)


def addition_from(candidate: str, start: str, end: str, label: str) -> str:
    i = exactly_one(candidate, start, "CANDIDATE_" + label + "_START")
    j = exactly_one(candidate, end, "CANDIDATE_" + label + "_END")
    if j <= i:
        raise Blocked("CANDIDATE_" + label + "_ORDER")
    return candidate[i:j]


def insert_once(source: str, needle: str, before: str, label: str) -> str:
    pos = exactly_one(source, needle, label)
    return source[:pos] + before + source[pos:]


def action_branches(source: str) -> set[str]:
    result = set(re.findall(r"\$action\s*===\s*['\"]([a-z_]+)['\"]", source))
    for group in re.findall(r"in_array\s*\(\s*\$action\s*,\s*\[([^\]]+)\]", source):
        result.update(re.findall(r"['\"]([a-z_]+)['\"]", group))
    return result


def page_branches(source: str) -> set[str]:
    return set(re.findall(r"\$page\s*===\s*['\"]([a-z_]+)['\"]", source))


def restore_post_handlers(live: str, candidate: str, notes: list[str]) -> str:
    if "journal_reverse" not in action_branches(live):
        if "$accountActions=" not in live:
            raise Blocked("ACCOUNT_AUTH_ANCHOR_MISSING")
        auth = re.findall(r"(?m)^.*\$accountActions=\[[^\]]+\];.*$", live)
        if len(auth) != 1:
            raise Blocked("ACCOUNT_AUTH_AMBIGUOUS")
        if "'journal_reverse'" not in auth[0]:
            updated = auth[0].replace("'journal',", "'journal','journal_reverse',", 1)
            if updated == auth[0]:
                raise Blocked("ACCOUNT_AUTH_UNKNOWN")
            live = live.replace(auth[0], updated, 1)
        block = addition_from(
            candidate, "        } elseif($action==='journal_reverse'){",
            "        } elseif($action==='party'){", "JOURNAL_REVERSE",
        )
        live = insert_once(live, "        } elseif($action==='party'){", block, "POST_PARTY")
        notes.append("journal_reverse")
    if "user_update" not in action_branches(live):
        auth = re.findall(
            r"(?m)^.*if\(\$action!=='password_change'\)\s*authorize\(.*$",
            live,
        )
        if len(auth) != 1:
            raise Blocked("USER_ROLE_AUTH_AMBIGUOUS")
        if "user_update" not in auth[0]:
            old = "$action==='user'?'users':'manage'"
            if old not in auth[0]:
                raise Blocked("USER_ROLE_AUTH_UNRECOGNIZED")
            repl = "in_array($action,['user','user_update'],true)?'users':'manage'"
            live = live.replace(auth[0], auth[0].replace(old, repl), 1)
        block = addition_from(
            candidate, "        } elseif($action==='user_update'){",
            "        } else bail('عملیات مجاز نیست.',403);", "USER_UPDATE",
        )
        live = insert_once(live, "        } else bail('عملیات مجاز نیست.',403);",
                           block, "POST_REJECT")
        notes.append("user_update")
    return live


def restore_get_handlers(live: str, candidate: str, notes: list[str]) -> str:
    if "chatgpt_reports" not in page_branches(live):
        block = addition_from(
            candidate, "    } elseif($page==='chatgpt_reports'){",
            "    } elseif($page==='approval_register'){", "CHATGPT_REPORTS",
        )
        live = insert_once(live, "    } elseif($page==='audit'){",
                           block, "GET_AUDIT_REPORT")
        notes.append("chatgpt_reports")
    if "approval_register" not in page_branches(live):
        block = addition_from(
            candidate, "    } elseif($page==='approval_register'){",
            "    } elseif($page==='audit'){", "APPROVAL_REGISTER",
        )
        live = insert_once(live, "    } elseif($page==='audit'){",
                           block, "GET_AUDIT_APPROVALS")
        notes.append("approval_register")
    missing = [x for x in ("chatgpt_reports", "approval_register") if x not in live]
    if missing:
        raise Blocked("GET_ROUTES_UNRESTORED")
    return live


def restore_navigation(live: str, notes: list[str]) -> str:
    needle = "'dashboard'=>'داشبورد',"
    additions = []
    for page, caption in (
        ("approval_register", "دفتر مصوبات"),
        ("chatgpt_reports", "گزارش‌های متنی ChatGPT"),
    ):
        nav_match = re.findall(r"(?m)^.*\$nav=\[.*$", live)
        if len(nav_match) != 1:
            raise Blocked("NAVIGATION_ANCHOR_AMBIGUOUS")
        if f"'{page}'=>" not in nav_match[0]:
            additions.append(f"'{page}'=>'{caption}',")
    if additions:
        i = exactly_one(live, needle, "NAV_DASHBOARD")
        live = live[:i + len(needle)] + "".join(additions) + live[i + len(needle):]
        notes.append("navigation")
    return live


def restore_helpers(live: str, candidate: str, notes: list[str]) -> str:
    if not re.search(r"\bfunction\s+positiveId\s*\(", live):
        lines = [line for line in candidate.splitlines()
                 if line.startswith("function positiveId(")]
        if len(lines) != 1:
            raise Blocked("POSITIVE_ID_HELPER_AMBIGUOUS")
        live = insert_once(live, "function money(", lines[0] + "\n",
                           "HELPER_MONEY")
        notes.append("positiveId")
    return live


def restore_ui(live: str, notes: list[str]) -> str:
    components = []
    if "formBegin('journal_reverse')" not in live:
        components.append("""    if($page==='journal' && in_array(role(),['admin','accountant'],true)){
        echo '<section><h2>برگشت کنترل‌شده سند مستقل</h2><p class="muted">سند اصلی حفظ می‌شود و برگشت نیازمند ثبت علت است.</p>';
        formBegin('journal_reverse');
        echo '<label>شناسه سند اصلی</label><input name="entry_id" type="number" min="1" required><label>علت برگشت</label><input name="reason" minlength="8" maxlength="200" required><label>تاریخ برگشت</label><input name="date" type="date" value="'.today().'" required><button>ثبت سند برگشتی</button></form></section>';
    }
""")
        notes.append("journal_reverse_form")
    if "formBegin('user_update')" not in live:
        components.append("""    if($page==='users'){
        authorize('users');
        echo '<section><h2>ویرایش و لغو دسترسی کاربران</h2>';
        foreach(q($db,'SELECT id,username,role,active FROM users ORDER BY id') as $row){
            if((int)$row['id']===actor())continue;
            echo '<div class="card"><h3>'.esc($row['username']).'</h3>';
            formBegin('user_update');
            echo '<input type="hidden" name="user_id" value="'.(int)$row['id'].'"><label>نقش</label><select name="role">';
            foreach(['viewer'=>'مشاهده‌گر','manager'=>'مدیر','accountant'=>'حسابدار','admin'=>'مدیر کل'] as $key=>$label)
                echo '<option value="'.$key.'"'.($key===$row['role']?' selected':'').'>'.$label.'</option>';
            echo '</select><label>وضعیت</label><select name="active"><option value="1"'.((int)$row['active']?' selected':'').'>فعال</option><option value="0"'.(!(int)$row['active']?' selected':'').'>غیرفعال</option></select><button>ثبت تغییر</button></form></div>';
        }
        echo '</section>';
    }
""")
        notes.append("user_update_form")
    if components:
        marker = "\n    layoutEnd();\n}catch(Throwable $e)"
        live = insert_once(live, marker, "\n" + "".join(components),
                           "FINAL_LAYOUT")
    return live


def validate_legacy(source: str, label: str) -> None:
    if not set(ROUTES).issubset(page_branches(source)):
        raise Blocked(label + "_V7_ROUTES_INCOMPLETE")
    if not set(ACTIONS).issubset(action_branches(source)):
        raise Blocked(label + "_V7_ACTIONS_INCOMPLETE")
    i = source.find("function record(")
    j = source.find("\nfunction ", i + 1)
    body = source[i:j if j > i else len(source)] if i >= 0 else ""
    if not re.search(r"\bzmPeriodGuard\s*\(\s*\$db\s*,\s*\$date\s*\)", body):
        raise Blocked(label + "_PERIOD_GUARD_MISSING")


def validate_stage(live: str, stage: str) -> None:
    validate_legacy(live, "LIVE")
    validate_legacy(stage, "STAGE")
    if not {"journal_reverse", "user_update"}.issubset(action_branches(stage)):
        raise Blocked("STAGE_ACTIONS_INCOMPLETE")
    if not {"approval_register", "chatgpt_reports"}.issubset(page_branches(stage)):
        raise Blocked("STAGE_GET_INCOMPLETE")
    if len(stage) < len(live):
        raise Blocked("STAGE_SHRANK")


def schema_ro_status(db_file: pathlib.Path) -> str:
    if db_file.is_symlink() or not db_file.is_file():
        return "missing_or_unsafe"
    try:
        uri = db_file.resolve().as_uri() + "?mode=ro"
        with sqlite3.connect(uri, uri=True) as connection:
            inv = {row[1] for row in connection.execute("PRAGMA table_info(invoices)")}
            paid = {row[1] for row in connection.execute("PRAGMA table_info(invoice_payments)")}
        return ("ready" if "posted_entry" in inv and "entry_id" in paid
                else "missing_reverse_columns")
    except (sqlite3.Error, OSError):
        return "unavailable"


def reconcile(live: str, candidate: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    validate_legacy(live, "LIVE")
    stage = restore_helpers(live, candidate, notes)
    stage = restore_post_handlers(stage, candidate, notes)
    stage = restore_get_handlers(stage, candidate, notes)
    stage = restore_navigation(stage, notes)
    stage = restore_ui(stage, notes)
    validate_stage(live, stage)
    return stage, notes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", required=True, type=pathlib.Path)
    parser.add_argument("--candidate", required=True, type=pathlib.Path)
    parser.add_argument("--out", required=True, type=pathlib.Path)
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args()
    try:
        if args.live.is_symlink() or not args.live.is_file():
            raise Blocked("UNSAFE_LIVE_FILE")
        original = args.live.read_bytes()
        digest = hashlib.sha256(original).hexdigest()
        if digest != args.expected_sha:
            raise Blocked("LIVE_SHA_CHANGED")
        candidate = args.candidate.read_text("utf-8")
        original_text = original.decode("utf-8")
        stage, notes = reconcile(original_text, candidate)
        # The caller must place --out in an owner-only private temporary directory.
        if args.out.exists() or args.out.is_symlink():
            raise Blocked("STAGE_ALREADY_EXISTS")
        args.out.write_text(stage, encoding="utf-8")
        args.out.chmod(0o600)
        print("ADDITIVE_STAGE=ready")
        print("ADDED_COMPONENTS=" + ",".join(notes))
        print("STAGE_SHA256=" + hashlib.sha256(stage.encode("utf-8")).hexdigest())
        print("STAGE_SCHEMA=" + schema_ro_status(args.live.parent / "management.sqlite3"))
        print("LIVE_SOURCE_EXPORTED=no")
        return 0
    except Blocked as exc:
        print("ADDITIVE_STAGE=blocked")
        print("BLOCK_REASON=" + str(exc))
        print("LIVE_SOURCE_EXPORTED=no")
        return 5


if __name__ == "__main__":
    sys.exit(main())
