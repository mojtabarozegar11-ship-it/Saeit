"""Evidence-bound continuous learning for MojPlayWin's private agent workforce.

Reads only main-site private operator outcomes; writes only a private evolution
journal. No network, deployment, subprocesses, code mutation, financial actions,
model training, publishing or cross-tenant access.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
from datetime import datetime, timezone

try:
    from .generation_factory import produce as produce_next_generation
except ImportError:  # Direct, isolated script execution from private cPanel Cron.
    from generation_factory import produce as produce_next_generation

try:
    from .gen65_runtime import operate as operate_gen65
except ImportError:  # Direct, isolated private Cron script.
    from gen65_runtime import operate as operate_gen65

PREFIX = Path("/home/zomorod2/.private_mojplaywin_main_agents")
AGENT_STATE = PREFIX / "v91_verified_main_port_20261018" / "operator_state"
HEALTH = PREFIX / "site_health_v11_port_20261018" / "last_scan.json"
EVOLUTION = PREFIX / "evolution_runtime_20261018"
TENANT = "mojplaywin-main"
MAX_RECORDS = 300
MAX_READ = 24000
MAX_OUTPUT = 30000
MAX_HISTORY = 96
POLICIES = {"baseline": (90, 1), "source_rigorous": (95, 2)}


def _safe_dir(path: Path) -> bool:
    return path.is_dir() and not path.is_symlink() and not (path.stat().st_mode & 0o077)


def _json(path: Path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_READ:
        return None
    try:
        value = json.loads(path.read_text("utf-8"))
        return value if isinstance(value, dict) else None
    except (ValueError, OSError, UnicodeError):
        return None


def _atomic(path: Path, data: dict) -> None:
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    if len(raw) > MAX_OUTPUT:
        raise ValueError("bounded_private_evolution_output_exceeded")
    fd, tmp = tempfile.mkstemp(prefix=".mpw-evol-", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as file:
            file.write(raw)
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.lexists(tmp):
            os.unlink(tmp)


def _scored_reviews() -> list[dict]:
    """Only hash-matched processed requests, generated drafts and reviewer results."""
    required = (AGENT_STATE, AGENT_STATE / "processed",
                AGENT_STATE / "drafts", AGENT_STATE / "quality_reviews")
    if not all(_safe_dir(p) for p in required):
        return []
    rows = []
    for path in sorted((AGENT_STATE / "processed").glob("*.json"))[:MAX_RECORDS]:
        request = _json(path)
        if not request or request.get("tenant") != TENANT or request.get("review_only") is not True:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:24]
        draft = _json(AGENT_STATE / "drafts" / (digest + ".json"))
        review = _json(AGENT_STATE / "quality_reviews" / (digest + ".json"))
        if not draft or not review or not isinstance(draft.get("draft"), dict):
            continue
        body = draft["draft"]
        if (body.get("tenant") != TENANT or body.get("published") is not False
                or review.get("tenant") != TENANT
                or review.get("status") not in ("review_ready_not_published", "needs_editorial_revision")):
            continue
        score = review.get("quality_score")
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 100:
            continue
        sources = body.get("sources", [])
        if not isinstance(sources, list):
            continue
        kind = request.get("kind", "research_digest")
        if kind not in ("research_digest", "product_blueprint"):
            continue
        rows.append({"id": digest, "kind": kind, "quality": float(score),
                     "source_count": len(sources),
                     "ready": review["status"] == "review_ready_not_published"})
    return rows


def _benchmark(rows: list[dict], quality: int, min_sources: int) -> dict:
    tp = tn = fp = fn = 0
    for row in rows:
        accept = row["quality"] >= quality and row["source_count"] >= min_sources
        ready = row["ready"]
        if accept and ready: tp += 1
        elif accept and not ready: fp += 1
        elif not accept and ready: fn += 1
        else: tn += 1
    # Wrongly accepting a draft is significantly worse than unnecessarily holding it.
    utility = (tp + tn - 4 * fp - fn) / max(1, len(rows))
    return {"observations": len(rows), "true_positive": tp, "true_negative": tn,
            "false_positive": fp, "false_negative": fn, "utility": round(utility, 6)}


def _compare(rows: list[dict], active: str) -> tuple[str, dict, str]:
    metrics = {name: _benchmark(rows, *values) for name, values in POLICIES.items()}
    if len(rows) < 12:
        return active, metrics, "insufficient_verified_outcomes"
    baseline = metrics[active]
    candidates = [(name, m) for name, m in metrics.items()
                  if name != active and m["false_positive"] <= baseline["false_positive"]
                  and m["utility"] >= baseline["utility"] + 0.10
                  and m["false_negative"] <= baseline["false_negative"] + 1]
    if not candidates:
        return active, metrics, "no_proven_policy_improvement"
    # One reversible preference change only; never alter code or grant permissions.
    winner, _ = max(candidates, key=lambda p: (p[1]["utility"], -p[1]["false_positive"], p[0]))
    return winner, metrics, "private_policy_improved_on_verified_outcomes"


def _health() -> dict:
    if not _safe_dir(HEALTH.parent):
        return {"state": "unavailable", "routes_checked": 0}
    data = _json(HEALTH)
    if not data or data.get("tenant") != TENANT or data.get("total_agents") != 11:
        return {"state": "unavailable", "routes_checked": 0}
    runs = data.get("runs", [])
    if not isinstance(runs, list) or len(runs) != 11 or len({r.get("code") for r in runs if isinstance(r, dict)}) != 11:
        return {"state": "invalid", "routes_checked": 0}
    return {"state": "observed", "routes_checked": 11,
            "ok": sum(r.get("status") == "ok" for r in runs),
            "warning": sum(r.get("status") == "warning" for r in runs),
            "error": sum(r.get("status") == "error" for r in runs)}


def calculate(rows: list[dict], previous: dict | None, health: dict) -> dict:
    old = previous or {}
    active = old.get("active_policy", "baseline")
    if active not in POLICIES:
        active = "baseline"
    new_policy, benchmark, decision = _compare(rows, active)
    observed = {r["id"] for r in rows}
    previous_ids = set(old.get("seen_ids", [])[:MAX_RECORDS]) if isinstance(old.get("seen_ids"), list) else set()
    history = old.get("history", [])
    if not isinstance(history, list):
        history = []
    epoch = min(10**7, max(0, int(old.get("epoch", 0))) + 1)
    history = history[-(MAX_HISTORY - 1):]
    now = datetime.now(timezone.utc).isoformat()
    history.append({"utc": now, "epoch": epoch, "verified_outcomes": len(rows),
                    "new_outcomes": len(observed - previous_ids), "active_policy": new_policy,
                    "decision": decision, "site_health": health.get("state", "unavailable")})
    return {"tenant": TENANT, "status": "active_private_learning",
            "observed_utc": now, "epoch": epoch, "master_generation": 64,
            "active_policy": new_policy, "prior_policy": active,
            "policy_changed": active != new_policy, "decision": decision,
            "benchmark": benchmark, "verified_outcome_count": len(rows),
            "new_verified_outcomes": len(observed - previous_ids),
            "seen_ids": sorted(observed)[:MAX_RECORDS],
            "history": history, "site_health": health,
            "self_modified_code": False, "executed_financial_actions": 0,
            "auto_published": False, "shared_runtime_modified": False,
            "requires_review_for_code_upgrade": True}


def cycle() -> dict:
    os.umask(0o077)
    if not (_safe_dir(PREFIX) and _safe_dir(AGENT_STATE.parent)
            and _safe_dir(AGENT_STATE)):
        raise RuntimeError("private_origin_not_verified")
    if EVOLUTION.exists():
        if not _safe_dir(EVOLUTION):
            raise RuntimeError("evolution_state_not_private")
    else:
        EVOLUTION.mkdir(mode=0o700)
    lock = EVOLUTION / "cycle.lock"
    if lock.is_symlink():
        raise RuntimeError("unsafe_evolution_lock")
    fd = os.open(str(lock), os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "another_evolution_cycle_running", "tenant": TENANT}
        state_file = EVOLUTION / "learning_state.json"
        previous = _json(state_file)
        if state_file.exists() and previous is None:
            raise RuntimeError("invalid_prior_evolution_state")
        if previous and previous.get("tenant") != TENANT:
            raise RuntimeError("cross_tenant_learning_state")
        rows = _scored_reviews()
        result = calculate(rows, previous, _health())
        _atomic(state_file, result)
        _atomic(EVOLUTION / "last_report.json",
                {key: result[key] for key in (
                    "tenant", "status", "observed_utc", "epoch", "master_generation",
                    "active_policy", "prior_policy", "policy_changed", "decision",
                    "benchmark", "verified_outcome_count", "new_verified_outcomes",
                    "site_health", "self_modified_code", "executed_financial_actions",
                    "auto_published", "shared_runtime_modified")})
        # Create real, compile-checked GEN65+ Python source in a private quarantine.
        # A new generation is NOT a live controller: no execution, imports, or
        # publishing occur. Existing minute cron drives this bounded factory.
        generation = produce_next_generation(
            EVOLUTION, rows,
            demonstrated_policy_improvement=(result["policy_changed"] is True
                and result["decision"] == "private_policy_improved_on_verified_outcomes"))
        # Execute SHA-attested Gen65 as a real but private read-only controller.
        # The owner enable flag controls operation; absent flags leave it disabled.
        gen65 = operate_gen65(EVOLUTION, rows, result["epoch"], result["observed_utc"])
        _atomic(EVOLUTION / "last_generation_report.json",
                {"tenant": TENANT, "generated_by_master": 64,
                 "generation": generation["generation"],
                 "factory_status": generation["status"],
                 "observed_utc": now if (now := result["observed_utc"]) else "",
                 "experimental_only": True, "production_changed": False,
                 "code_sha256": generation.get("code_sha256"),
                 "verified_outcomes": len(rows)})
        return {**{key: result[key] for key in (
                    "status", "epoch", "active_policy", "decision",
                    "verified_outcome_count", "new_verified_outcomes", "site_health")},
                "next_generation": generation["generation"],
                "generation_factory_status": generation["status"],
                "generation_experimental_only": gen65["status"] != "gen65_operational_private",
                "gen65_runtime_status": gen65["status"],
                "gen65_active_private_generation": (65 if gen65["status"] == "gen65_operational_private" else None)}
    finally:
        os.close(fd)


def main():
    cli = argparse.ArgumentParser()
    mode = cli.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = cli.parse_args()
    if args.check:
        result = {"status": "private_evolution_source_ready", "tenant": TENANT,
                  "public_release": False}
    else:
        result = cycle()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
