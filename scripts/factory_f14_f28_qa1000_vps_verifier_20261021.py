#!/usr/bin/env python3
"""Verify 1,024-case technical QA against the actual nonpublic VPS product files."""
import hashlib
import json
import os
from pathlib import Path
import sys

def check(root_name, report_name, wanted_sha, archive_sha):
    root=Path(root_name)
    assert root.is_dir() and not root.is_symlink()
    incoming=Path(report_name)
    assert incoming.is_file() and not incoming.is_symlink()
    payload=incoming.read_bytes()
    assert hashlib.sha256(payload).hexdigest()==wanted_sha
    q=json.loads(payload)
    assert q["schema"]=="saeit.factory.f14-f28-strict-qa.v1"
    assert q["financial_oracle_scenarios"]>=1024
    assert q["financial_malicious_and_invalid_rejected"]>=256
    assert q["game_simulations"]>=1024
    assert q["game_deterministic_replay_verified"]>=1024
    assert q["game_assertion_failures"]==0
    assert q["all_technical_checks_passed"] is True
    for k in ("specialist_review_passed","rights_cleared","commercially_approved",
              "payment_enabled","publicly_published","owner_publication_approval","release_eligible"):
        assert q[k] is False
    folder=root/"product-commercial-pilots"/("f14-f28-"+archive_sha[:24])
    assert folder.is_dir() and not folder.is_symlink()
    receipt=json.loads((folder/"receipt.json").read_text())
    manifest=json.loads((folder/"manifest.json").read_text())
    assert receipt["archive_sha256"]==archive_sha
    assert receipt["source_commits"]==q["source_commits"]
    assert manifest["source_commits"]==q["source_commits"]
    assert receipt["private_only"] is True
    assert receipt["payment_enabled"] is False
    assert receipt["commercially_approved"] is False
    hashes=q["source_file_sha256"]
    assert len(hashes)==7 and hashes==manifest["file_hashes"]
    for name,wanted in hashes.items():
        path=folder/name
        assert path.is_file() and not path.is_symlink()
        assert hashlib.sha256(path.read_bytes()).hexdigest()==wanted,name
    out=root/"product-commercial-pilots"/("quality-evidence-"+wanted_sha[:24]+".json")
    assert not out.is_symlink()
    if out.exists():
        assert out.read_bytes()==payload
    else:
        with out.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(out,0o600)
    assert hashlib.sha256(out.read_bytes()).hexdigest()==wanted_sha
    print("FACTORY_QA_1000_VPS_PRODUCT_HASH_MATCH=PASS")
    print("FACTORY_QA_1000_VPS_PERSISTED_RECEIPT_SHA256="+wanted_sha)
    print("FACTORY_QA_1000_COMMERCIAL_RELEASE=BLOCKED")
if __name__=="__main__":
    assert len(sys.argv)==5
    check(*sys.argv[1:])
