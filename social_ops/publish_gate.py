"""Fail-closed publication readiness checks. No network or publishing actions."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "social_ops/brands.json"
CONNECTIONS = ROOT / "social_ops/connections.json"

def readiness(brand_id, channel, draft, connections):
    problems = []
    if draft.get("brand") != brand_id:
        problems.append("brand_mismatch")
    if not draft.get("title") or not draft.get("text"):
        problems.append("missing_content")
    if draft.get("status") != "approved_for_publication":
        problems.append("not_approved")
    if not draft.get("originality_checked"):
        problems.append("originality_not_checked")
    if not draft.get("rights_checked"):
        problems.append("rights_not_checked")
    account = connections.get(brand_id, {}).get(channel, {})
    if account.get("verified") is not True:
        problems.append("account_not_verified")
    if account.get("authorized_to_publish") is not True:
        problems.append("publication_not_authorized")
    if account.get("integration_tested") is not True:
        problems.append("integration_not_tested")
    if not account.get("account_id"):
        problems.append("missing_account_id")
    return {"ready": not problems, "blockers": problems}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand", choices=["personal", "company", "mojplaywin"])
    parser.add_argument("--channel")
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    connections = json.loads(CONNECTIONS.read_text(encoding="utf-8"))
    results = {}
    for brand in registry["brands"]:
        if args.brand and brand["id"] != args.brand:
            continue
        channels = [args.channel] if args.channel else brand["channels"]
        for channel in channels:
            if channel not in brand["channels"]:
                raise SystemExit(f"Unsupported channel {channel} for {brand['id']}")
            sample = {"brand": brand["id"], "status": "draft_requires_review",
                      "title": "sample", "text": "sample"}
            results[f"{brand['id']}:{channel}"] = readiness(
                brand["id"], channel, sample, connections)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    if any(not result["ready"] for result in results.values()):
        raise SystemExit(2)

if __name__ == "__main__":
    main()
