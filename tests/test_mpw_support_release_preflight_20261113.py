"""MojPlayWin support release preflight: contract must fail closed on changes."""
import json
from pathlib import Path

from scripts.mpw_support_release_preflight_20261113 import ROOT, CONTRACT, audit, git_blob_sha


def test_source_integrity_and_release_guards_are_valid():
    result = audit()
    assert result["source_preflight_passed"], result["source_problems"]
    assert result["source_files_checked"] == 7
    assert result["production_deployment_authorized"] is False
    assert result["production_ready"] is False
    assert result["public_pages_verified"] == 0
    assert len(result["host_baselines_pending"]) == 6


def test_release_plan_cannot_claim_verification_without_host_evidence():
    document = json.loads((ROOT / CONTRACT).read_text(encoding="utf-8"))
    assert document["deployment_authorized"] is False
    assert len(document["website_probes"]) == 3
    assert all(probe["status"] == "unverified" for probe in document["website_probes"])
    assert all(entry["expected_live_sha256"] is None for entry in document["files"])
    assert len({entry["path"] for entry in document["files"]}) == 7


def test_a_modified_blob_would_fail_the_sha_guard():
    data = b"official customer contact is mojplaywin@gmail.com"
    assert git_blob_sha(data) != git_blob_sha(data + b" altered")
    document = json.loads((ROOT / CONTRACT).read_text(encoding="utf-8"))
    first = document["files"][0]
    source = (ROOT / first["path"]).read_bytes()
    assert git_blob_sha(source) == first["source_git_blob_sha"]
    assert git_blob_sha(source + b"changed") != first["source_git_blob_sha"]
