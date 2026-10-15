# Astra V2 — independent research radar (experimental, isolated)

Purpose: identify fresh **research questions** from independent reading of
two publicly available USDA NASS RSS feeds and the official NASS newsroom. No human prompt, buyer order,
paid API, or pre-written candidate list is required for the source scan.

This is **not** a commercial product generation, validation or deployment
feature. The source agencies publish statistics/news, not proof of buyers
willing to pay for software. All three fixed sources come from the **same publisher**;
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
endpoints for USDA NASS News, Today's Reports and the official NASS newsroom, with fixed timeout, strict
response size, no redirects, no proxies, and no external feed URLs.

To test an offline RSS or first-party HTML fixture (no network):

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

The GitHub Actions workflow uses no secrets: it runs offline unit tests and a separate public-source network smoke test, entirely on disposable GitHub runners.
It is deliberately NOT attached to production or the private VPS clock.
Live reports are only kept in the runner's temporary directory, not uploaded as public artifacts. The fixed public sources may be stale, unavailable, or change formats:
failures are reported instead of fabricating research.

Future rollout requires a **separate authorized isolated VPS/runner deployment**,
a bounded cadence and retention policy, review of legal/source terms, and
independent review of at least three truly distinct evidence publishers.
Never pipe this report directly into the live factory's intake or store.


## Private VPS execution status and bounded fresh-source signals (15 October 2026)

The installed private `githubops` cron runs at minute 17 every six hours,
entirely separately from `ASTRA_V2_PRIVATE_RND_TICK`. GitHub Actions tests
verify the existing factory cron remains unchanged; no public store, payments,
live database migration, or factory queue is touched. The VPS uses Python
3.8.2, which is supported by the private runner.

The daily report `daily-YYYYMMDD.json` is immutable. Subsequent research
within a different six-hour UTC window is saved as
`retry-YYYYMMDD-SLOT.json` (SLOT is 0,1,2,3), also immutable. Repeating the
same slot is a no-op. The initial 15 October report with one unavailable source
was preserved and an independent retry successfully downloaded all three
fixed public sources and found two *research questions*.

For a fresh retry, the radar consults only safely parsed private reports from
the last 30 days (bounded to 160 reports), and annotates each topic with a
count of newly observed headline-source SHA-256 references.
`novel_source_signals_30d` **does not mean** new paying customers,
verified independent publishers, willingness to pay, new commercial goods,
or objective product quality. If all headline references were seen before,
the report records zero novelty rather than manufacturing another product.
Historical private reports are never overwritten or silently deleted.

Current scope remains research-only and subject to independent domain,
market, licensing, and field validation. PR 178 is still a draft; the dedicated
private VPS staging workflow does not authorize merging the broader
Astra/0049 branch or releasing its products.
