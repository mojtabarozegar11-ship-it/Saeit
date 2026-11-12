#!/usr/bin/env python3
"""Private cPanel additive PHP overlay PREVIEW: zero production file writes.

Run only over a pinned SHA-256 of the existing live app. Proposed PHP is
streamed via stdin from the reviewed source branch. The live app and
candidate are never printed or copied to GitHub; php -l checks stdin.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

LIVE = Path("/home/zomorod2/.private/zomorod-business/app.php")
MAX_BYTES = 1_000_000


def stop(reason: str) -> None:
    print("OVERLAY_PREVIEW=" + reason)
    raise SystemExit(3)


def unique(text: str, needle: str, label: str) -> None:
    count = text.count(needle)
    if count != 1:
        stop("ANCHOR_" + label + "_COUNT_" + str(count))


def section(text: str, start: str, end: str, label: str) -> str:
    unique(text, start, label + "_BEGIN")
    unique(text, end, label + "_END")
    left = text.index(start)
    right = text.index(end)
    if right <= left:
        stop("SECTION_ORDER_" + label)
    fragment = text[left:right]
    if not fragment.startswith(start) or len(fragment) > 7000:
        stop("SECTION_LENGTH_" + label)
    return fragment


def apply(live: str, proposed: str) -> tuple[str, list[tuple[str, str, str]]]:
    if "genetics_project_register" in live or "$page==='genetics_center'" in live:
        stop("GENETICS_PARTIALLY_INSTALLED_MANUAL_RECONCILIATION")
    changes: list[tuple[str, str, str]] = []

    def replace_once(needle: str, replacement: str, label: str) -> None:
        nonlocal live
        unique(live, needle, label)
        if replacement == needle or needle not in replacement:
            stop("NOT_ADDITIVE_" + label)
        live = live.replace(needle, replacement, 1)
        changes.append((needle, replacement, label))

    nav = "'projects'=>'پروژه‌ها','mojplaywin'"
    replace_once(
        nav,
        "'projects'=>'پروژه‌ها','genetics_center'=>'ژنتیک و اصلاح نژاد جانوران','mojplaywin'",
        "NAV",
    )

    action = "        } elseif($action==='project'){"
    action_fragment = section(
        proposed,
        "        } elseif($action==='genetics_project_register'){",
        action,
        "ADMIN_ACTION",
    )
    replace_once(action, action_fragment + action, "ADMIN_ACTION_INSERT")

    insertion_anchor = "            $db->prepare('INSERT INTO projects(title,owner,state,budget) VALUES(?,?,?,?)')"
    guard_fragment = section(
        proposed,
        "            // Reserve the genetics dossier ID for its idempotent admin-only registration action.",
        insertion_anchor,
        "RESERVED_ID",
    )
    if "str_starts_with(trim($title),'ZM-AGRC-GEN-1405-001')" not in guard_fragment:
        stop("RESERVED_ID_GUARD_INVALID")
    replace_once(insertion_anchor, guard_fragment + insertion_anchor, "GENERIC_PROJECT_GUARD")

    page_anchor = "    } elseif($page==='projects'){"
    page_fragment = section(
        proposed, "    } elseif($page==='genetics_center'){", page_anchor, "DOSSIER_ROUTE"
    )
    replace_once(page_anchor, page_fragment + page_anchor, "DOSSIER_ROUTE")

    # These two additions remain within existing branches, leaving all legacy
    # accounting and management statements bit-for-bit unchanged.
    dashboard_boundary = "    } elseif($page==='mojplaywin'){"
    dashboard_fragment = (
        "        echo '<section><h2>مرکز جامع ژنتیک و اصلاح نژاد جانوران"
        "</h2><p>پرونده مطالعاتی و اقتصادی؛ ظرفیت‌ها و برآوردها غیرمصوب هستند."
        "</p><a href=\"?page=genetics_center\">مشاهده پرونده پروژه</a></section>';\n"
        "        if(role()==='admin'){\n"
        "            echo '<section><h2>ورود از صفحات داخلی سایت میزبان</h2>"
        "<p>پارس وب سرور ← ورود | عضویت ← سرویس‌های من ← هاست زمرد ملل ← ورود به cPanel.</p>"
        "<a target=\"_blank\" rel=\"noopener noreferrer\" href=\"https://parswebserver.com/\">"
        "آغاز از سایت میزبان</a></section>';\n"
        "        }\n"
    )
    replace_once(
        dashboard_boundary,
        dashboard_fragment + dashboard_boundary,
        "DASHBOARD_LINKS",
    )

    project_form = (
        "        if(role()!=='viewer'){echo '<section><h2>افزودن پروژه</h2>';"
        "formBegin('project');"
    )
    project_fragment = (
        "        echo '<section><h2>پرونده مرکز ژنتیک جانوران</h2>"
        "<p>شناسه ZM-AGRC-GEN-1405-001؛ برنامه مفهومی، بودجه غیرمصوب،"
        " پیشرفت اجرایی مستند صفر.</p><a href=\"?page=genetics_center\">"
        "مشاهده جزئیات و وضعیت ثبت در دفتر پروژه‌ها</a></section>';\n"
    )
    replace_once(project_form, project_fragment + project_form, "PROJECTS_LINK")

    # Independent additive proof: reverse every small insertion and recover
    # byte-exact legacy source (no preserved content was overwritten).
    candidate = live
    for before, after, name in reversed(changes):
        unique(candidate, after, name + "_REVERSE")
        candidate = candidate.replace(after, before, 1)
    return live, changes, candidate


def main() -> None:
    if len(sys.argv) != 2 or not re.fullmatch(r"[0-9a-f]{64}", sys.argv[1]):
        stop("INVALID_BASELINE_HASH")
    if not LIVE.is_file() or LIVE.is_symlink():
        stop("LIVE_APP_UNSAFE")
    meta = LIVE.stat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid() or os.geteuid() == 0:
        stop("INVALID_FILE_OWNER")
    original = LIVE.read_bytes()
    if len(original) > MAX_BYTES:
        stop("LIVE_APP_TOO_LARGE")
    actual = hashlib.sha256(original).hexdigest()
    print("OVERLAY_LIVE_APP_SHA256=" + actual)
    if actual != sys.argv[1]:
        stop("LIVE_BASELINE_CHANGED")
    incoming = sys.stdin.buffer.read(MAX_BYTES + 1)
    if not incoming or len(incoming) > MAX_BYTES:
        stop("PROPOSED_APP_INVALID_SIZE")
    try:
        before = original.decode("utf-8")
        proposed = incoming.decode("utf-8")
    except UnicodeDecodeError:
        stop("NON_UTF8_PHP")
    candidate, changes, roundtrip = apply(before, proposed)
    if roundtrip != before:
        stop("LEGACY_CONTENT_ROUNDTRIP_FAILED")
    if candidate.count("genetics_project_register") != 1:
        stop("ACTION_COUNT_INVALID")
    if candidate.count("genetics_center')") < 1:
        stop("DOSSIER_ROUTE_MISSING")

    php = shutil.which("php") or "/opt/cpanel/ea-php82/root/usr/bin/php"
    if not Path(php).is_file():
        stop("PHP_LINTER_MISSING")
    parsed = subprocess.run(
        [php, "-l"], input=candidate.encode("utf-8"),
        capture_output=True, timeout=18, check=False,
    )
    if parsed.returncode != 0:
        stop("CANDIDATE_PHP_SYNTAX_INVALID")
    print("OVERLAY_ADDITIONS_COUNT=" + str(len(changes)))
    print("OVERLAY_LEGACY_CONTENT_PRESERVED=true")
    print("OVERLAY_CANDIDATE_SHA256=" + hashlib.sha256(candidate.encode("utf-8")).hexdigest())
    print("OVERLAY_CANDIDATE_PHP_LINT=PASS")
    print("OVERLAY_LIVE_SOURCE_EXPORTED=no")
    print("OVERLAY_LIVE_FILES_MODIFIED=no")
    print("OVERLAY_LIVE_DATABASE_TOUCHED=no")
    print("OVERLAY_DEPLOYED=no")
    print("OVERLAY_PREVIEW=PASS_READ_ONLY")


if __name__ == "__main__":
    main()
