#!/usr/bin/env python3
"""Private MojPlayWin newsroom agent interface; safe for controlled cron use.

Examples (run from repository root; NO credentials in command history):
  python scripts/mpw_newsletter_cli.py init
  python scripts/mpw_newsletter_cli.py draft --json private-input.json
  python scripts/mpw_newsletter_cli.py approve --id 1 --editor OWNER
  python scripts/mpw_newsletter_cli.py publish-due
  python scripts/mpw_newsletter_cli.py stats

Approving is an intentional authorized human action. Generators/review agents
may create drafts and run quality checks, but cannot approve their own work.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from core.mojplaywin_newsroom import Newsroom, private_db_path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=("init", "draft", "approve", "publish-due", "stats"))
    p.add_argument("--json", dest="input_file", type=Path)
    p.add_argument("--id", dest="story_id", type=int)
    p.add_argument("--editor", default="")
    p.add_argument("--when", default="", help="Optional ISO 8601 scheduled date, timezone required")
    p.add_argument("--db", type=Path, help="Explicit private absolute SQLite location")
    args = p.parse_args()
    db = args.db or private_db_path()
    store = Newsroom(db)
    if args.action == "init":
        connection = store._connect(write=True)
        connection.close()
        print("MOJPLAYWIN_NEWSROOM_INITIALIZED=private")
    elif args.action == "draft":
        if args.input_file is None or not args.input_file.is_file():
            p.error("draft requires --json JSON_FILE")
        source = args.input_file.resolve()
        if str(source).startswith(str(ROOT / "core" / "templates")):
            p.error("Do not place drafts in public templates")
        article = json.loads(source.read_text(encoding="utf-8"))
        story_id, score = store.create_draft(article)
        print(json.dumps({"story_id": story_id, "quality_score": score,
                          "requires_review": True, "can_approve": score >= 90}))
    elif args.action == "approve":
        if not args.story_id or not args.editor:
            p.error("approve requires --id and --editor")
        approved = store.approve(args.story_id, args.editor, args.when)
        print(json.dumps({"approved": approved}))
        if not approved:
            sys.exit(2)
    elif args.action == "publish-due":
        published = store.publish_due()
        print(json.dumps({"published": published, "requires_prior_approval": True}))
    elif args.action == "stats":
        print(json.dumps(store.stats(), ensure_ascii=False))


if __name__ == "__main__":
    main()
