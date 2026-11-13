"""Bounded read-only source inventory for Moj Coin/Living Cities and demo trading.

Never treats a build script as a game server, a cBot source file as an active
broker session, or a calculated SHA256 as independent supply-chain validation.
Only known public repository paths are inspected; no secrets/network access.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


# These are previously verified, repository-local *source* paths.
# Living Cities game runtime lives outside this public source snapshot and
# cannot be certified from the presence of its old deployment scripts.
SOURCES = {
    "games": (
        ("scripts/living_cities_static_publish.py", "release_script"),
        ("scripts/living_cities_static_upgrade.py", "release_script"),
        ("scripts/mpw_living_cities_global_upgrade.py", "release_script"),
    ),
    "trading": (
        ("trading/MojTradeOmegaXDemoBot.cs", "demo_cbot_source"),
        ("trading/Mojtaba.Bot.Ai.csproj", "build_contract"),
        ("trading/README.md", "risk_boundary_document"),
    ),
}
MAX_SOURCE_SIZE = 256 * 1024


def _read_source(root: Path, relative_path: str) -> dict:
    path = root / relative_path
    # File paths are fixed in the module, never interpolated from a request.
    # Refuse symlinks, including a symlinked parent; do not follow an alias
    # into private files or files outside the Django repository.
    current = root
    for part in Path(relative_path).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("DOMAIN_SOURCE_SYMLINK_DENIED")
    if not path.exists():
        return {"path": relative_path, "present": False}
    if not path.is_file():
        raise ValueError("DOMAIN_SOURCE_NOT_REGULAR_FILE")
    stat = path.stat()
    if stat.st_size <= 0 or stat.st_size > MAX_SOURCE_SIZE:
        raise ValueError("DOMAIN_SOURCE_SIZE_NOT_ALLOWED")
    raw = path.read_bytes()
    if len(raw) != stat.st_size:
        raise ValueError("DOMAIN_SOURCE_CHANGED_DURING_READ")
    return {
        "path": relative_path,
        "present": True,
        "bytes": len(raw),
        "sha256_observed": hashlib.sha256(raw).hexdigest(),
        # A nonempty file and a hash are not functional QA.
        "content_reviewed_or_tested": False,
    }


def inspect_domain_source(domain: str) -> dict:
    """Inspect bounded repository source for one of two previously unmapped domains."""
    if type(domain) is not str or domain not in SOURCES:
        raise ValueError("DOMAIN_SOURCE_UNKNOWN_DOMAIN")
    root = Path(__file__).resolve().parents[1]
    checked = []
    for relative_path, role in SOURCES[domain]:
        report = _read_source(root, relative_path)
        checked.append({"role": role, **report})
    present = sum(bool(entry["present"]) for entry in checked)
    if domain == "games":
        evidence_class = "living_cities_release_scripts_only"
        runtime_source_verified = False
    else:
        evidence_class = "canonical_demo_cbot_source_and_build_contract_only"
        runtime_source_verified = False
    return {
        "domain": domain,
        "evidence_class": evidence_class,
        "source_files_expected": len(checked),
        "source_files_present": present,
        "files": checked,
        "source_hashes_calculated_locally": True,
        "independent_source_signatures_verified": False,
        "deployed_runtime_verified": runtime_source_verified,
        "backtest_or_gameplay_verified": False,
        "trading_live_enabled": False,
        "purchase_or_token_disbursement_enabled": False,
        "settled_profit_or_rewards_verified": False,
        "private_runtime_or_broker_connector_needed": True,
    }
