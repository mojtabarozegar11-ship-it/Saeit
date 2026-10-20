# Factory Production Workbench — 1,000 usable bindings

**Status:** GitHub source and 1,000-command fixture QA implemented. Actual VPS installation is
only established when a release run prints `WORKBENCH_1000_PRIVATE_INSTALL=PASS` and
independent readback verifies both SHA-256 digests in `verification.json`.
A successful GitHub CI alone is **not** evidence of VPS installation.

## Honest scope

This is **40 registered product families × 25 functional, offline production-support operations**.
Each `F01-T01` through `F40-T25` is independently addressable and executes deterministic
Python code. The family binding specializes the tool's context, ownership, audit identity
and production queues. The 25 operations share implementations; these are **not**
1,000 separate AI models or 1,000 native full-product manufacturing engines.
They do not create saleable products, independently review a product, authorize commerce,
access websites, issue payments, or assert external scientific facts.

## Available operations per family

| Number | Tool | Actual result |
|---|---|---|
| T01 | Unicode text cleaner | Normalized, whitespace-clean text |
| T02 | Markdown outline extractor | Heading list and levels |
| T03 | Text metrics | Word counts, uniqueness, line counts |
| T04 | Keyword histogram | Ranked frequency table |
| T05 | Checklist extractor | Checked and unchecked task records |
| T06 | CSV field profiler | Row, column, null and uniqueness metrics |
| T07 | CSV row deduplicator | Deduplicated table and removed count |
| T08 | CSV stable sorter | Table sorted by named field |
| T09 | CSV exact-value filter | Matching subset and count |
| T10 | CSV-to-JSON converter | Parsed record objects |
| T11 | JSON-to-CSV converter | Tabular serialized rows |
| T12 | Nested JSON flattener | Dot-path object projection |
| T13 | JSON key-change comparator | Added, deleted and altered keys |
| T14 | Required-field validator | Specific missing required fields |
| T15 | Safe dictionary merger | Composed, immutable input replacement |
| T16 | SHA-256 text checksum | Hexadecimal digest and byte count |
| T17 | Content-anchored asset manifest | SHA-256 file-content manifest from supplied text |
| T18 | License completeness audit | Missing licenses and attribution markers (not a rights certification) |
| T19 | Asset path safety audit | Rejected unsafe paths |
| T20 | Escaped HTML metadata builder | Safely escaped title and description markup |
| T21 | Search-friendly slug builder | ASCII URL slug |
| T22 | Requirements evidence matrix | Verified-evidence entries and gaps |
| T23 | Quantified risk register | Risk ranking by 1–5 likelihood × impact |
| T24 | Noncommercial release checklist | Missing technical evidence; release remains unauthorized |
| T25 | Production work breakdown | Seven planned steps for each named deliverable |

## CLI and registry

Run only inside an authorized private VPS working directory with the canonical
`forty_families.json` registry. A registered tool accepts a small JSON object;
it never executes arbitrary supplied code.

```bash
PY="$HOME/factory-runtime/.venv/bin/python"
ROOT="$HOME/factory-runtime"
PRIVATE="$ROOT/private/autonomous-product-cycle"
REGISTRY="$ROOT/operations/forty-family-master/forty_families.json"
TOOL="$ROOT/operations/production-workbench-1000/runner.py"

# Create input in a dedicated private directory and invoke one concrete tool.
mkdir -p "$PRIVATE/production-toolkit/jobs"
chmod 700 "$PRIVATE/production-toolkit/jobs"
printf '%s\n' '{"text":"  Original   product  description  "}' > "$PRIVATE/production-toolkit/jobs/request.json"
"$PY" -B "$TOOL" --registry "$REGISTRY" --tool-id F01-T01 \
  --workspace "$PRIVATE/production-toolkit/jobs" \
  --input-file "$PRIVATE/production-toolkit/jobs/request.json" \
  --output-file "$PRIVATE/production-toolkit/jobs/result.json"
```

No product quality-approval is inferred from the `technical_checks_complete` field.
For a saleable item, the independent 12-stage product passport, real evidence
and the live Django FactoryReleaseGate requirements remain mandatory.

## Release safety

The installer is restricted to the non-root `githubops` account, uses a lock,
a backup and rollback, replaces only private workbench files, runs 1,000
deterministic fixture checks, verifies the canonical 40-family registry, compares
cron state before and after, and never changes cPanel sites or checkout.

* Source: `scripts/factory_1000_workbench.py`
* Tests: `tests/test_factory_1000_workbench.py`
* Installer: `deploy/install_factory_1000_workbench.sh`
* CI workflow: `.github/workflows/vps-factory-1000-workbench-release-20261020.yml`

Only report `live_installed: true` after a genuine VPS install and proof.
