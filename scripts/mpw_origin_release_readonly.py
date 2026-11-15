#!/usr/bin/env python3
"""Bounded, PII-free, source-only cPanel Passenger inventory (never a release gate).

Run via pinned SSH using python3 -B -. No DB, external API, Django import,
network calls, subprocesses, file writes or user-provided paths. File booleans
are observations, not legal eligibility or live payment proofs.
"""
from __future__ import annotations

import json
from pathlib import Path

HOME = Path("/home/zomorod2")
DOCROOT = HOME / "mojplaywin.com"
# Two observed/claimed roots are candidates, not proven MojPlayWin production.
# The live direct Django check on 2026-11-15 reached HOME/Saeit, while the
# historic MojPlayWin deploy script expects HOME/Saeit-staging. The Passenger
# UAPI root fingerprint did not attest to either path. Never select by guess.
APP = HOME / "Saeit-staging"
COMPANY_CANDIDATE = HOME / "Saeit"
MAX_READ_BYTES = 200_000
PROBES = (
    ("passenger_mapping", DOCROOT, "passenger_wsgi.py", ("Saeit-staging",)),
    ("passenger_config", DOCROOT, ".htaccess", ()),
    ("django_urls", APP, "config/urls.py", ('path("store/",',)),
    ("three_product_routes", APP, "config/urls.py", ('brand_product_detail',)),
    ("prop_route", APP, "config/urls.py", ("moj_prop_public",)),
    ("signals_route", APP, "config/urls.py", ("signal_interest",)),
    ("withdrawal_route", APP, "config/urls.py", ("interest_withdrawal",)),
    ("store_template", APP, "core/templates/mojplaywin/store.html",
     ("/store/product/72/", "/store/product/225/", "/store/product/879/")),
    ("store_detail_view", APP, "core/mojplaywin_product_detail.py",
     ("def brand_product_detail", "MPW_HOSTS")),
    ("store_detail_template", APP, "core/templates/mojplaywin/product_detail.html",
     ("purchase_available", "MojPlayWin")),
    ("prop_lead_view", APP, "core/moj_prop_public.py",
     ("def moj_prop_public_interest",)),
    ("signal_lead_view", APP, "core/signal_interest_views.py",
     ("def signal_interest",)),
    ("consent_lead_model", APP, "core/signal_interest_models.py",
     ("class CommercialInterest",)),
    ("withdrawal_view", APP, "core/interest_withdrawal.py",
     ("def withdrawal", "csrf_protect")),
    ("withdrawal_template", APP, "core/templates/core/interest_withdrawal.html",
     ('method="post"',)),
    # Separate candidate inventory prevents mistaking the known Saeit Django
    # company app for the historic MojPlayWin Saeit-staging target.
    ("company_candidate_manage", COMPANY_CANDIDATE, "manage.py", ()),
    ("company_candidate_urlconf", COMPANY_CANDIDATE, "config/urls.py", ()),
    ("company_candidate_store", COMPANY_CANDIDATE,
     "core/templates/mojplaywin/store.html", ()),
    ("company_candidate_prop", COMPANY_CANDIDATE,
     "core/moj_prop_public.py", ()),
    ("company_candidate_signals", COMPANY_CANDIDATE,
     "core/signal_interest_views.py", ()),
)


def status(root: Path, relative: str, markers: tuple[str, ...]) -> str:
    """No symlink traversal, unbounded read, full source output or privilege change."""
    if not root.is_dir() or root.is_symlink():
        return "root_unavailable"
    path = root
    for part in Path(relative).parts:
        path = path / part
        if path.is_symlink():
            return "unsafe_symlink"
    if not path.is_file():
        return "missing"
    try:
        if path.stat().st_size > MAX_READ_BYTES:
            return "oversized"
        contents = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return "unreadable"
    return "matched" if all(x in contents for x in markers) else "marker_missing"


def inspect(probes=PROBES) -> dict:
    observations = {
        name: status(root, relative, markers)
        for name, root, relative, markers in probes
    }
    return {
        "kind": "readonly_passenger_source_inventory",
        "merchant": "mojplaywin.com",
        "candidate_roots": {
            "historical_brand_app": "Saeit-staging",
            "direct_django_check_app": "Saeit",
        },
        "candidate_root_is_live_passenger_app_proven": False,
        "host_fingerprint_checked_by_workflow": True,
        "file_probe_count": len(observations),
        "matched_file_probes": sum(s == "matched" for s in observations.values()),
        "observations": observations,
        "payment_authorized": False,
        "production_isolation_verified": False,
        "release_authorized": False,
        "invoice_or_order_accessed": False,
        "server_files_modified": False,
    }


if __name__ == "__main__":
    print(json.dumps(inspect(), sort_keys=True, ensure_ascii=False))
