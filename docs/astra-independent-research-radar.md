# Astra V2 — independent research radar (experimental, isolated)

Purpose: identify fresh **research questions** from independent reading of
two publicly available USDA NASS RSS feeds. No human prompt, buyer order,
paid API, or pre-written candidate list is required for the feed scan.

This is **not** a commercial product generation, validation or deployment
feature. The source agencies publish statistics/news, not proof of buyers
willing to pay for software. Both feeds come from the **same publisher**;
independent market corroboration remains missing. The output is a private
research-only shortlist and all build/publish/payment flags are false.

## Local usage (Python 3.11+, stdlib only)

Run the no-network tests from the repository root:

```bash
python3 -m unittest discover -s tests -p 'test_astra_independent_research_radar.py' -v
```

Run research manually in a disposable / segregated workspace:

```bash
mkdir -p /tmp/astra-radar-private
chmod 700 /tmp/astra-radar-private
python3 scripts/astra_independent_research_radar.py \
  --fetch --output /tmp/astra-radar-private/report-20261015.json
```

Note: a later run needs a **different output filename**, because overwriting
private review history is forbidden. The script only requests exact HTTPS
endpoints for USDA NASS News and Today's Reports, with fixed timeout, strict
response size, no redirects, no proxies, and no external feed URLs.

To test an offline feed fixture (no network):

```bash
python3 scripts/astra_independent_research_radar.py \
  --fixture /path/to/sample.xml --source nass_news \
  --now-utc 2026-10-15T12:00:00Z \
  --output /tmp/astra-radar-private/offline-review.json
```

## What the report DOES and DOES NOT mean

- Uses public *article headline*, HTTPS source URL and publication date only;
  not whole copied articles. Exact source references are retained.
- Performs deterministic keyword routing into water/land, procurement, farm
  markets, and data education research questions.
- Suppresses stale/future/off-site entries, unsafe XML, duplicate references.
- Provisional **topic priority** is a simple triage heuristic, NOT quality,
  demand, price, profitability or probability of purchase.
- Rejects any assumption that two NASS feeds constitute two publishers.
- Produces NO product, queue item, customer assertion, public listing,
  payment instruction, cPanel edit, GitHub deployment or VPS change.
- Requires independent competitor study, user research, rights/domain review
  and credible willingness-to-pay signals **before** commercial promotion.

The GitHub Actions workflow is a no-secret, no-network offline test only.
It is deliberately NOT attached to production or the private VPS clock.
The fixed public feeds may occasionally be unavailable or change formats:
failures are reported instead of fabricating research.

Future rollout requires a **separate authorized isolated VPS/runner deployment**,
a bounded cadence and retention policy, review of legal/source terms, and
independent review of at least three truly distinct evidence publishers.
Never pipe this report directly into the live factory's intake or store.
