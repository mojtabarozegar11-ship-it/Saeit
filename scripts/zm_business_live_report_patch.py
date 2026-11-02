#!/usr/bin/env python3
"""Deterministic, additive patch for the *currently active* PHP business desk.

Does not replace the source with a stale repository copy. Fails closed if any
of the three stable existing release points is missing, doubled or patched.
"""
import argparse
import os
from pathlib import Path
import sys

ANCHORS = (
    ("'audit'=>'ردپای عملیات'",
     "'chatgpt_reports'=>'گزارش‌های متنی ChatGPT','audit'=>'ردپای عملیات'"),
    ("if($key==='users'&&role()!=='admin')continue;",
     "if(($key==='users'||$key==='chatgpt_reports')&&role()!=='admin')continue;"),
    ("    } elseif($page==='audit'){",
     "    } elseif($page==='chatgpt_reports'){\n"
     "        authorize('users');\n"
     "        $module=__DIR__.'/chatgpt_reports.php';\n"
     "        if(!is_file($module)||is_link($module))bail('ماژول گزارش در دسترس نیست.',503);\n"
     "        require_once $module;\n"
     "        zmBusinessChatgptReports($private);\n"
     "    } elseif($page==='audit'){"),
)


def patch(source):
    if not 10000 <= len(source.encode("utf-8")) <= 500000:
        raise ValueError("PHP_SOURCE_SIZE_UNEXPECTED")
    if "chatgpt_reports" in source:
        raise ValueError("PHP_REPORT_ROUTE_ALREADY_PRESENT")
    for old, new in ANCHORS:
        if source.count(old) != 1:
            raise ValueError("PHP_PATCH_ANCHOR_MISSING_OR_DUPLICATE")
        source = source.replace(old, new, 1)
    return source


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args(argv)
    try:
        source = args.source
        if not source.is_file() or source.is_symlink():
            raise ValueError("INVALID_PHP_SOURCE")
        raw = source.read_text(encoding="utf-8")
        after = patch(raw)
        if args.output:
            if os.environ.get("ZM_REPORT_PATCH_STAGE") != "1":
                raise ValueError("PHP_PATCH_STAGE_GATE_DISABLED")
            target = args.output
            if not target.is_absolute() or target.exists() or target.is_symlink():
                raise ValueError("PATCH_OUTPUT_NOT_NEW_ABSOLUTE_FILE")
            if not target.parent.is_dir() or target.parent.is_symlink():
                raise ValueError("PATCH_OUTPUT_DIRECTORY_UNSAFE")
            fd = os.open(str(target), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                out.write(after)
                out.flush()
                os.fsync(out.fileno())
        print("LIVE_PHP_ADDITIVE_PATCH=" + ("STAGED" if args.output else "VALIDATED_READ_ONLY"))
        print("PATCHED_EXPECTED_ANCHORS=3")
        print("FINANCIAL_DB_TOUCHED=no")
        return 0
    except (ValueError, OSError, UnicodeError) as exc:
        print("LIVE_PHP_ADDITIVE_PATCH=BLOCKED", file=sys.stderr)
        print("ERROR_CLASS=" + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
