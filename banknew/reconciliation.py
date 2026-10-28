"""Read-only ledger-to-settlement reconciliation for MOJ Pay.

Inputs must come from an independently authenticated settlement source.
This does not authenticate providers, credit accounts, sign, transfer value,
confirm chain finality, or approve unsettled transactions.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from banknew.ledger_core import Ledger, LedgerError, _ASSET, _hash, _reference, _units


class ReconciliationError(LedgerError):
    """Unsafe statement, mapping or reconciliation state."""


def _normalize_statements(statements: Sequence[dict]) -> list[dict[str, str]]:
    if not isinstance(statements, (list, tuple)) or len(statements) > 10000:
        raise ReconciliationError("Statement must be a bounded list.")
    normalized = []
    for row in statements:
        if not isinstance(row, dict) or set(row) != {
            "reference", "asset", "direction", "units"
        }:
            raise ReconciliationError("Invalid statement fields.")
        reference = _reference(row["reference"], "provider reference")
        asset = row["asset"]
        if not isinstance(asset, str) or not _ASSET.fullmatch(asset):
            raise ReconciliationError("Invalid asset identifier.")
        direction = row["direction"]
        if direction not in ("IN", "OUT"):
            raise ReconciliationError("Invalid settlement direction.")
        normalized.append({
            "reference": reference, "asset": asset, "direction": direction,
            "units": str(_units(row["units"])),
        })
    return normalized


def reconcile(ledger: Ledger, statements: Sequence[dict],
              cash_accounts: Mapping[str, str]) -> dict:
    """Compare provider entries with cash movements in one consistent DB snapshot.

    Cash accounts map each asset to its normal-debit clearing account. One
    external reference must identify exactly one movement. Multi-asset
    exchanges require separately verifiable settlement references.
    """
    batch = _normalize_statements(statements)
    if not isinstance(cash_accounts, dict) or not cash_accounts:
        raise ReconciliationError("Cash account map required.")
    if len(cash_accounts) > 32 or len(set(cash_accounts.values())) != len(cash_accounts):
        raise ReconciliationError("Ambiguous cash account mapping.")
    for asset, account in cash_accounts.items():
        if not isinstance(asset, str) or not _ASSET.fullmatch(asset):
            raise ReconciliationError("Invalid mapped asset.")
        _reference(account, "cash account")
    for row in batch:
        if row["asset"] not in cash_accounts:
            raise ReconciliationError("Unmapped statement asset.")

    if ledger.db.in_transaction:
        raise ReconciliationError("Cannot reconcile inside another transaction.")
    ledger.db.execute("BEGIN")
    try:
        integrity = ledger.audit()
        for asset, account in cash_accounts.items():
            stored = ledger.db.execute(
                "SELECT asset,normal_side FROM accounts WHERE account_id=?", (account,)
            ).fetchone()
            if stored is None or stored != (asset, "D"):
                raise ReconciliationError("Cash account must be debit-normal.")
        account_names = tuple(cash_accounts.values())
        placeholders = ",".join("?" for _ in account_names)
        query = (
            "SELECT j.seq,j.external_ref,p.account_id,p.asset,p.side,p.units "
            "FROM journals j JOIN postings p ON p.journal_seq=j.seq "
            f"WHERE p.account_id IN ({placeholders}) "
            "ORDER BY j.seq,p.line_number"
        )
        by_journal: dict[int, dict] = {}
        for seq, ref, account, asset, side, value in ledger.db.execute(
            query, account_names
        ):
            details = by_journal.setdefault(seq, {"reference": ref, "deltas": {}})
            delta = _units(value) * (1 if side == "D" else -1)
            details["deltas"][asset] = details["deltas"].get(asset, 0) + delta
        recorded = []
        issues = []
        for seq, item in by_journal.items():
            if len(item["deltas"]) != 1:
                issues.append({"code": "multi_asset_settlement",
                               "reference": item["reference"], "journal_seq": seq})
                continue
            asset, delta = next(iter(item["deltas"].items()))
            if delta == 0:
                issues.append({"code": "zero_net_cash_journal",
                               "reference": item["reference"], "journal_seq": seq})
                continue
            recorded.append({
                "reference": item["reference"], "asset": asset,
                "direction": "IN" if delta > 0 else "OUT",
                "units": str(abs(delta)), "journal_seq": seq,
            })

        ledger_refs: dict[str, list[dict]] = {}
        for row in recorded:
            ledger_refs.setdefault(row["reference"], []).append(row)
        statement_refs: dict[str, list[dict]] = {}
        for row in batch:
            statement_refs.setdefault(row["reference"], []).append(row)
        matched = 0
        for reference in sorted(set(ledger_refs) | set(statement_refs)):
            booked = ledger_refs.get(reference, [])
            declared = statement_refs.get(reference, [])
            if len(booked) > 1:
                issues.append({"code": "duplicate_ledger_reference",
                               "reference": reference, "count": len(booked)})
            if len(declared) > 1:
                issues.append({"code": "duplicate_statement_reference",
                               "reference": reference, "count": len(declared)})
            if len(booked) > 1 or len(declared) > 1:
                continue
            if not booked:
                issues.append({"code": "missing_ledger_entry", "reference": reference})
            elif not declared:
                issues.append({"code": "missing_provider_statement",
                               "reference": reference,
                               "journal_seq": booked[0]["journal_seq"]})
            elif any(booked[0][key] != declared[0][key] for key in (
                "asset", "direction", "units"
            )):
                issues.append({
                    "code": "settlement_mismatch", "reference": reference,
                    "statement": declared[0],
                    "ledger": {key: booked[0][key] for key in (
                        "asset", "direction", "units", "journal_seq"
                    )},
                })
            else:
                matched += 1
        issues.sort(key=lambda row: (row["reference"], row["code"]))
        return {
            "status": "balanced" if not issues else "unreconciled",
            "matched": matched,
            "statement_count": len(batch),
            "ledger_cash_movements": len(recorded),
            "issues": issues,
            "ledger_head_hash": integrity["head_hash"],
            "statement_digest": _hash(sorted(
                batch, key=lambda row: (
                    row["reference"], row["asset"], row["direction"], row["units"]
                )
            )),
            "source_authentication": "not_performed_by_this_module",
        }
    finally:
        ledger.db.execute("ROLLBACK")
