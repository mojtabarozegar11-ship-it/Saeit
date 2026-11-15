#!/usr/bin/env python3
"""Read-only, fail-closed Moj Prop 0042..0045 source/DB release preflight.

SOURCE_READY does not mean production-ready or paid. --verify-release needs
a private snapshot from the actual target database plus a separately signed
isolated restore rehearsal. Does not deploy, migrate, mail, charge or SSH.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

if __package__:
    from .mojprop_db_release_evidence import (
        verify_database_restore_evidence, MissingDatabaseRestoreEvidence,
    )
else:
    from mojprop_db_release_evidence import (
        verify_database_restore_evidence, MissingDatabaseRestoreEvidence,
    )

_MIGRATIONS = (
    ("0042_mojprop_offer.py", "0041_mojprop_request"),
    ("0043_mojprop_digital_inquiry.py", "0042_mojprop_offer"),
    ("0044_mojprop_acceptance_evidence.py", "0043_mojprop_digital_inquiry"),
    ("0045_mojprop_delivery_evidence.py", "0044_mojprop_acceptance_evidence"),
)
_REQUIRED = {
    "core/models.py": ("class MojPropRequest(", "class MojPropOffer(",
                       "class MojPropDeliveryEvidence("),
    "core/admin.py": ("validate_status_change(", "class MojPropOfferAdmin(",
                      "class MojPropDeliveryEvidenceAdmin("),
    "core/mojprop_views.py": ("mojprop_intake(", "mojprop_receipt_status(",
                              "product_id", "CATALOG_INQUIRY_PRODUCTS"),
    "core/mojprop_quote_views.py": ("def customer_quote(",),
    "config/urls.py": ("moj-prop-quote/<str:token>/", "moj-prop-intake/"),
    "core/mojprop_receipts.py": ("verify_receipt_token(",),
}
_WORKFLOW = ".github/workflows/mojplaywin-moj-prop-deploy.yml"
_OWNER_GUARD = ("if: github.event_name == 'workflow_dispatch' && "
                "inputs.owner_approved_static_release == true")


class CommercialSchemaPreflightDenied(RuntimeError):
    pass


def _source(root: Path, name: str) -> str:
    target = root / name
    if target.is_symlink() or not target.is_file() or target.stat().st_size > 2_000_000:
        raise CommercialSchemaPreflightDenied("required source is missing or unsafe: " + name)
    try:
        code = target.read_text(encoding="utf-8")
        if name.endswith(".py"):
            compile(code, str(target), "exec")
    except (SyntaxError, UnicodeError) as exc:
        raise CommercialSchemaPreflightDenied("required source fails parsing: " + name) from exc
    return code


def source_readiness(root: Path) -> dict:
    if not isinstance(root, Path) or root.is_symlink() or not root.is_dir():
        raise CommercialSchemaPreflightDenied("unsafe source root")
    checked = []
    for relative, markers in _REQUIRED.items():
        code = _source(root, relative)
        if any(marker not in code for marker in markers):
            raise CommercialSchemaPreflightDenied("missing commercial source guard: " + relative)
        checked.append(relative)
    for file, parent in _MIGRATIONS:
        name = "core/migrations/" + file
        body = _source(root, name)
        if (f'("core", "{parent}")' not in body
                and f"('core', '{parent}')" not in body):
            raise CommercialSchemaPreflightDenied("broken commercial migration parent: " + file)
        checked.append(name)
    workflow = _source(root, _WORKFLOW)
    deploy = re.search(r"(?m)^  deploy:\s*$", workflow)
    if not deploy:
        raise CommercialSchemaPreflightDenied("owner-gated production job missing")
    head = workflow[deploy.end():].split("\n    steps:", 1)[0]
    if _OWNER_GUARD not in head or "workflow_dispatch:" not in workflow.split("\njobs:",1)[0]:
        raise CommercialSchemaPreflightDenied("unsafe automatic Moj Prop production deployment")
    checked.append(_WORKFLOW)
    return {
        "source_ready": True,
        "production_release_ready": False,
        "checked_files": checked,
        "required_migrations": [file for file, _ in _MIGRATIONS],
        "reason": "Independent database restore and live environment remain unverified.",
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--verify-release", action="store_true")
    p.add_argument("--backup-root", type=Path)
    p.add_argument("--run-id")
    p.add_argument("--commit")
    p.add_argument("--database-identity-sha256")
    args = p.parse_args(argv)
    try:
        report = source_readiness(args.repo_root.resolve())
        if args.verify_release:
            key = os.environ.get("MOJPROP_INDEPENDENT_RESTORE_VERIFIER_KEY", "")
            if (not args.backup_root or not args.run_id or not args.commit
                    or not args.database_identity_sha256 or len(key) < 32):
                raise CommercialSchemaPreflightDenied(
                    "independent runtime DB restore proof is not configured"
                )
            report["restore_proof"] = verify_database_restore_evidence(
                root=args.backup_root, run_id=args.run_id,
                source_commit=args.commit,
                database_identity_sha256=args.database_identity_sha256,
                verifier_key=key.encode("utf-8"),
            )
            # A valid proof does not prove current live route, wallet, legal,
            # production DB identity, deployment rollback or checkout readiness.
            report["reason"] = (
                "Signed database rehearsal checked. Live runtime identity and "
                "release approval remain independent production blockers."
            )
    except (CommercialSchemaPreflightDenied, MissingDatabaseRestoreEvidence) as exc:
        print(json.dumps({"source_ready": False,
                          "production_release_ready": False,
                          "blocked": str(exc)}, sort_keys=True))
        return 3
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
