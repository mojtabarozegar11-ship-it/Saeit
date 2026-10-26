#!/usr/bin/env python3
"""Private CLI. Never attach unprotected to a web endpoint or public cron."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from social_hub.catalog import catalogue
from social_hub.store import Store
from social_hub.service import connection_status, run_one
from social_hub.adapters import Blocked, Uncertain

def main(argv=None):
    parser = argparse.ArgumentParser(description="Omnichannel operator; outbound off by default")
    parser.add_argument("--db", help="Absolute path to private SQLite DB. Or SOCIAL_HUB_PRIVATE_DB.")
    sub = parser.add_subparsers(dest="command",required=True)
    sub.add_parser("catalog")
    sub.add_parser("summary")
    sub.add_parser("connections")
    reg = sub.add_parser("register")
    for n in ("brand","platform","destination"):
        reg.add_argument("--"+n, required=True)
    reg.add_argument("--public-url",default="")
    reg.add_argument("--instance",default="")
    reg.add_argument("--actor",required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--account",required=True)
    verify.add_argument("--proof",required=True)
    verify.add_argument("--actor",required=True)
    draft = sub.add_parser("draft")
    draft.add_argument("--account",required=True)
    draft.add_argument("--content-file",required=True)
    draft.add_argument("--scheduled-at")
    draft.add_argument("--actor",required=True)
    approve = sub.add_parser("approve")
    approve.add_argument("--post",required=True)
    approve.add_argument("--actor",required=True)
    cancel = sub.add_parser("cancel")
    cancel.add_argument("--post",required=True)
    cancel.add_argument("--actor",required=True)
    do = sub.add_parser("dispatch-one")
    do.add_argument("--post",required=True)
    do.add_argument("--execute",action="store_true")
    do.add_argument("--actor",default="private-worker")
    args = parser.parse_args(argv)
    if args.command == "catalog":
        print(json.dumps(catalogue(),ensure_ascii=False,indent=2))
        return 0
    location = args.db or os.getenv("SOCIAL_HUB_PRIVATE_DB")
    if not location:
        print(json.dumps({"status":"blocked","reason":"SOCIAL_HUB_PRIVATE_DB not configured"}))
        return 2
    try:
        db = Store(location)
        try:
            if args.command == "summary": result = db.summary()
            elif args.command == "connections": result = connection_status(db)
            elif args.command == "register":
                result = {"account_id":db.add_account(brand=args.brand,
                    platform_key=args.platform,destination=args.destination,
                    public_url=args.public_url,instance=args.instance,actor=args.actor)}
            elif args.command == "verify":
                db.verify_account(args.account,proof=args.proof,actor=args.actor)
                result = {"status":"verified","account_id":args.account}
            elif args.command == "draft":
                content = json.loads(Path(args.content_file).read_text(encoding="utf-8"))
                result = {"post_id":db.draft(account_id=args.account,content=content,
                          schedule_at=args.scheduled_at,actor=args.actor)}
            elif args.command == "approve":
                db.approve(args.post,args.actor)
                result = {"status":"approved","post_id":args.post}
            elif args.command == "cancel":
                db.revoke(args.post,args.actor)
                result = {"status":"cancelled","post_id":args.post}
            elif args.command == "dispatch-one":
                result = run_one(db,args.post,execute=args.execute,actor=args.actor)
            else: raise Blocked("Unsupported operation")
        finally:
            db.close()
    except (Blocked,Uncertain,ValueError,FileNotFoundError,OSError) as exc:
        print(json.dumps({"status":"blocked","reason":str(exc)},ensure_ascii=False))
        return 2
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
