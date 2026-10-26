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
from social_hub.service import connection_status, run_one, run_due
from social_hub.adapters import Blocked, Uncertain
from social_hub.diagnostics import record_one, SUPPORTED as READ_ONLY_PROVIDERS
from social_hub.credential_vault import load_private_import, plan_import, import_batch, disconnect_batch, create_private_template
from social_hub.onboarding import preview as preview_onboarding, register as register_onboarding

def main(argv=None):
    parser = argparse.ArgumentParser(description="Omnichannel operator; outbound off by default")
    parser.add_argument("--db", help="Absolute path to private SQLite DB. Or SOCIAL_HUB_PRIVATE_DB.")
    sub = parser.add_subparsers(dest="command",required=True)
    sub.add_parser("catalog")
    sub.add_parser("summary")
    sub.add_parser("connections")
    for command in ("batch-preview","batch-register"):
        batch=sub.add_parser(command)
        batch.add_argument("--manifest-file",required=True,
                           help="Owner-authored token-free JSON; NEVER contains private OAuth credentials")
        batch.add_argument("--actor",default="owner-cli:manual")
    template=sub.add_parser("credential-template")
    template.add_argument("--output-private-file",required=True)
    for name in ("credential-import-preview","credential-import"):
        provision=sub.add_parser(name)
        provision.add_argument("--input-private-file",required=True,
                 help="Root-owned mode-0600 JSON input; never pass secrets on the command line")
        provision.add_argument("--vault-file",required=True,
                 help="Private mode-0600 JSON vault outside public_html")
        provision.add_argument("--replace",action="store_true",
                 help="Explicitly rotate credentials that already exist")
        provision.add_argument("--confirm",action="store_true")
        provision.add_argument("--actor",default="owner-cli:credential-import")
    disconnect=sub.add_parser("credential-disconnect")
    disconnect.add_argument("--account",action="append",required=True)
    disconnect.add_argument("--vault-file",required=True)
    disconnect.add_argument("--confirm",action="store_true")
    disconnect.add_argument("--actor",default="owner-cli:credential-disconnect")
    diagnostics = sub.add_parser("test-readonly")
    diagnostics.add_argument("--account",required=True)
    diagnostics.add_argument("--confirm",action="store_true")
    diagnostics.add_argument("--actor",default="owner-cli:check")
    reg = sub.add_parser("register")
    for n in ("brand","platform","destination"):
        reg.add_argument("--"+n, required=True)
    reg.add_argument("--public-url",default="")
    reg.add_argument("--instance",default="")
    reg.add_argument("--actor",required=True)
    suspension = sub.add_parser("suspend-account")
    suspension.add_argument("--account",required=True)
    suspension.add_argument("--confirm",action="store_true")
    suspension.add_argument("--actor",default="owner-cli:suspend")
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
    due = sub.add_parser("dispatch-due")
    due.add_argument("--execute",action="store_true")
    due.add_argument("--limit",type=int,default=5)
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
            elif args.command == "credential-template":
                result=create_private_template(db,args.output_private_file)
            elif args.command in ("credential-import-preview","credential-import"):
                manifest=load_private_import(args.input_private_file)
                if args.command=="credential-import-preview":
                    result=plan_import(db,manifest,vault_file=args.vault_file,
                                       replace=args.replace)
                else:
                    if not args.confirm:
                        raise Blocked("Explicit --confirm required for private credential provisioning")
                    result=import_batch(db,manifest,vault_file=args.vault_file,
                                        actor=args.actor,replace=args.replace)
            elif args.command == "credential-disconnect":
                if not args.confirm:
                    raise Blocked("Explicit --confirm required for credential disconnection")
                result=disconnect_batch(db,args.account,vault_file=args.vault_file,
                                        actor=args.actor)
            elif args.command == "test-readonly":
                if not args.confirm:
                    raise Blocked("Read-only API test requires explicit --confirm")
                result = record_one(db,args.account,actor=args.actor)
            elif args.command == "connections": result = connection_status(db)
            elif args.command in ("batch-preview","batch-register"):
                manifest=json.loads(Path(args.manifest_file).read_text(encoding="utf-8"))
                if args.command == "batch-preview":
                    result=preview_onboarding(db,manifest)
                else:
                    result=register_onboarding(db,manifest,actor=args.actor)
            elif args.command == "register":
                result = {"account_id":db.add_account(brand=args.brand,
                    platform_key=args.platform,destination=args.destination,
                    public_url=args.public_url,instance=args.instance,actor=args.actor)}
            elif args.command == "suspend-account":
                if not args.confirm:
                    raise Blocked("Explicit --confirm required before suspending an owned account")
                result=db.suspend_account(args.account,actor=args.actor)
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
            elif args.command == "dispatch-due":
                result = run_due(db,limit=args.limit,execute=args.execute)
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
