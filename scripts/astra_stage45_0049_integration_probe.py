"""Prove Stage45 selector against *actual migrated 0049 SQLite* in CI only.

Synthetic sources are NOT verified market evidence. Does not enable builds.
Never invoke on a live or owner database; hard-coded ephemeral CI restriction.
"""
from datetime import datetime, timezone
import importlib.util
import os
from pathlib import Path
import sqlite3
from django.conf import settings
from django.utils import timezone as django_timezone
from core.models import FactoryQueueItem, DiscoverySnapshot


def run():
    path = Path(str(settings.DATABASES["default"]["NAME"])).resolve()
    if (
        os.environ.get("SAEIT_ENV") != "ci"
        or os.environ.get("ASTRA_0049_SYNTHETIC_PROOF") != "1"
        or "astra-0049-ephemeral" not in path.name
        or not path.is_file()
        or os.environ.get("DATABASE_URL") is None
    ):
        raise RuntimeError("SYNTHETIC_0049_PROOF_REQUIRES_DISPOSABLE_CI_SQLITE")
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as conn:
        recorded = conn.execute(
            "SELECT count(*) FROM django_migrations "
            "WHERE app='core' AND name='0049_astra_stage45_research_queue'"
        ).fetchone()[0]
    if recorded != 1 or FactoryQueueItem.objects.exists():
        raise RuntimeError("SYNTHETIC_0049_PROOF_REQUIRES_EMPTY_MIGRATED_QUEUE")

    first = FactoryQueueItem.objects.create(key="discovery:ASTRA-H001", kind="discovery")
    other = FactoryQueueItem.objects.create(key="discovery:ASTRA-H002", kind="discovery")
    stamp = django_timezone.now()
    domains = (
        ("example.com", "problem"),
        ("example.org", "willingness_to_pay"),
        ("example.net", "comparison"),
        ("example.com", "feasibility"),
    )
    for n, (domain, claim) in enumerate(domains):
        DiscoverySnapshot.objects.create(
            hypothesis=first,
            url=f"https://{domain}/synthetic-{n}",
            content_hash=f"{n+1:064x}",
            retrieved_at=stamp,
            record={"claim_type":claim, "illustrative_only":True},
        )
    DiscoverySnapshot.objects.create(
        hypothesis=other,
        url="https://example.edu/should-not-cross-pollinate",
        content_hash="d"*64,
        retrieved_at=stamp,
        record={"claim_type":"willingness_to_pay", "illustrative_only":True},
    )

    script = Path(__file__).resolve().with_name("astra_research_evidence_adapter.py")
    spec = importlib.util.spec_from_file_location("stage45_disposable_adapter", script)
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    score = {key: 80 for key in (
        "problem_intensity", "demand", "differentiation",
        "feasibility", "margin", "distribution", "strategic_fit")}
    gates = {key: True for key in (
        "lawful", "rights_reviewed", "build_capability_available",
        "distribution_path_available")}
    def candidate(key, queue_key):
        return {"opportunity_key":key, "astra_queue_key":queue_key,
                "problem":"Synthetic farm decision scenario; no real customer was interviewed",
                "assessments":score.copy(), "gates":gates.copy()}

    rows_before = DiscoverySnapshot.objects.count()
    report = adapter.evaluate_db(
        path,
        [candidate("a-eligible", first.key), candidate("b-unrelated", "missing-key")],
        datetime.now(timezone.utc).isoformat(),
    )
    by_key = {row["opportunity_key"]: row for row in report["candidates"]}
    ready = by_key["a-eligible"]
    isolated = by_key["b-unrelated"]
    # Explicitly synthetic snapshots must never qualify an opportunity for
    # market review. Earlier fixtures accidentally treated them as evidence.
    assert ready["status"] == "RESEARCH_REQUIRED", ready
    assert ready["distinct_source_domains_preliminary"] == 0
    assert ready["observed_claim_types"] == []
    assert "PROBLEM_OR_WILLINGNESS_SIGNAL_MISSING" in ready["blockers"]
    assert isolated["status"] == "RESEARCH_REQUIRED"
    assert isolated["distinct_source_domains_preliminary"] == 0
    assert report["bridge_audit"]["astra_0049_schema_available"]
    assert report["bridge_audit"]["astra_snapshots_examined"] == 4
    assert report["bridge_audit"]["astra_snapshots_eligible"] == 0
    assert report["bridge_audit"]["astra_snapshots_synthetic_rejected"] == 4
    assert report["bridge_audit"]["bridge_writes_to_factory"] == 0
    assert DiscoverySnapshot.objects.count() == rows_before
    assert all(
        not row["build_authorized"] and not row["publish_authorized"]
        and not row["payment_authorized"]
        and not row["evidence_verified_independently"]
        for row in report["candidates"]
    )
    assert not FactoryQueueItem.objects.exclude(
        build_authorized=False, publish_authorized=False,
        payment_authorized=False, evidence_verified_independently=False
    ).exists()
    print("ASTRA_0049_TYPED_EVIDENCE_BRIDGE=PASS")
    print("ASTRA_0049_EXACT_HYPOTHESIS_ISOLATION=PASS")
    print("ASTRA_0049_SYNTHETIC_CLAIMS_NOT_PROMOTED=PASS")
    print("ASTRA_0049_NO_MANUFACTURING_AUTHORIZATION=true")
    print("ASTRA_0049_NO_PAYMENT_OR_PUBLICATION_AUTHORIZATION=true")
    print("ASTRA_0049_SYNTHETIC_DATA_ONLY=true")
