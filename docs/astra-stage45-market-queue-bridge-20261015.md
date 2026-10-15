# Astra Stage45: linking research triage to the 0049 shadow queue

**Scope:** Private research only; no order required, no product built, no live factory migration, no sales authorization.

## What was implemented

`scripts/astra_stage45_market_queue_bridge.py` composes two existing, unchanged, fail-closed tools:

1. `astra_stage45_research_backlog.analyze()` checks an existing isolated 0049 SQLite queue and deduplicated preliminary evidence.
2. `astra_market_readiness_gate.assess()` checks bounded structured market packets: explicit sources and observed competitor features, but **cannot attest** them.

The joined output is a research task list, with each queue row still `RESEARCH_REQUIRED`, `build_authorized=false`, `publish_authorized=false`, `payment_authorized=false`. Neither its product identity nor any alleged market fact becomes verified automatically.

## Crucial distinction: nine-source prototype has NO proven legacy ID

The existing water-and-land prototype packet uses product key `farm_water_land_margin_audit_v1`. The historical 0048 factory has 209 unpublished products, now represented by potential separate `research:legacy-product:<id>` keys. **We do not know which, if any, historical product corresponds to the water-and-land prototype.** Never guess from title similarity, zip name, source count or row order.

With no bindings file, the bridge processes the packet but reports it under `unlinked_market_product_keys`; all historical queue entries remain research-only and unmatched.

An *optional* private binding sidecar has this shape (the numbers are synthetic examples only and MUST NOT be used as real production mappings):

```json
{
  "bindings": [
    {
      "queue_key": "research:legacy-product:10",
      "product_key": "farm_water_land_margin_audit_v1"
    }
  ]
}
```

This simply declares an **unverified** pairing for human investigation. The output explicitly says `linkage_independently_verified=false`. An actual release process would require separate ownership/provenance validation and independent review, none of which this code grants.

## Offline usage — ONLY on an authorized, isolated 0049 database

```bash
python3 scripts/astra_stage45_market_queue_bridge.py \
  --db /path/to/isolated-0049-shadow.sqlite3 \
  --market-dir research \
  --now-utc 2026-10-15T13:00:00Z \
  --output /path/to/private-market-triage.json
```

Only where a correct private source-to-product correspondence is independently available, add `--bindings /path/to/private-bindings.json`. The output is `0600`; the tool refuses output overwrite of its database and input files, symlinked packets, broken 0049 schemas, unauthorized queue states, malformed inputs and excessive batches.

Local regression tests:

```bash
python3 -m unittest discover -s tests -p 'test_astra_stage45_market_queue_bridge.py' -v
```

## No-order scope, and what remains

This can be invoked on a fixed schedule independently of orders **only after a properly authorized 0049 shadow database exists**. It does not install a scheduler, fetch web pages, interview buyers, migrate the existing 0048 runtime, assign a commercial score, manufacture, set the 90%-discount price or publish. Existing factory and prior 0049 deployment safety gates remain unchanged.

**Next independent acceptance requirements:** prove a current live backup/rollback, obtain approved isolated 0049 shadow provisioning, confirm exact product ID crosswalk, validate actual buyer and competitor evidence, and verify specialist QA and checkout before release. A GitHub CI pass proves code behavior on synthetic/isolated fixtures, not VPS 0049 activation or product-market fit.
