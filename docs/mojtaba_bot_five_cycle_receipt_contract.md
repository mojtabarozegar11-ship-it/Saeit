# mojtaba.bot.ai — A–E hourly receipts (C03)

## Purpose and status

This contract allows the five existing hourly automation tasks to hand off
**already-executed, Git-committed changes** to the one central ledger. The
receipt is not the action, is not a sales confirmation, and does not prove a
public product was released. Until deployment/hosting and delivery have
independent proof, the commercial KPI is **not verified**.

The five lanes each target 50 distinct successful changes **per hourly run**
(250 total). Report exact numerator/denominator; never fill missing slots with
inspections, tasks created, reports, duplicated commits or synthetic test files.

## Canonical work handoff

1. Complete allowed real work first, not just queueing it. Use the existing
   GitHub connector to create or update the actual eligible artifact on the
   existing authorized source branch and read the resulting commit SHA.
2. Obtain the exact SHA-256 of the changed artifact **as it exists in that
   commit**; do not use Git blob SHA-1 or an uncommitted local file.
3. For each distinct accepted artifact, prepare one action with exactly these
   fields:

```json
{
  "action_id": "A-20261112-R17-001",
  "item": "Specific work item and artifact",
  "kind": "deliverable_created",
  "before": "Specific previous state, independently observable",
  "change": "The material modification actually made",
  "after": "Result with readback evidence",
  "evidence": [
    "commit:<40 hexadecimal characters>",
    "path:deliverables/books/unique-artifact.md",
    "sha256:<64 hexadecimal characters>"
  ]
}
```

4. Place **1–50 actual distinct actions** in a committed manifest, one new
   manifest per hourly execution, with this *exact* top-level shape:

```json
{
  "schema_version": "1.0",
  "engine": "mojtaba.bot.ai",
  "cycle": "A",
  "run_id": "A-20261112T160000Z",
  "actions": []
}
```

The empty array above is a **schema illustration only**, never a valid
submission. The manifest must be a tracked, unchanged Git file at
`runtime/cycle_receipts/<LANE>/<UNIQUE_RUN_ID>.json`, using the same checked
out repository/branch that contains its artifact commits. Set `cycle`,
`run_id` and each `action_id` to the correct lane. Never backdate or reuse
a previous hourly manifest.

5. Execute (in an authorized checkout or the guarded central runner):

```sh
python3 deploy/mojtaba_bot_cycle_receipt_bridge.py \
  --cycle A \
  --manifest runtime/cycle_receipts/A/A-20261112T160000Z.json \
  --state /path/to/authorized/persistent/central_cycle_state.json
```

The bridge enforces a committed clean manifest, lane ownership, and 1–50
unique action IDs and artifact paths. The worker verifies immutable Git bytes,
Git ancestry, change attribution, fresh production of accepted source
artifacts, global replay rules and counts 50/50 only when all 50 are
independently accepted.

## Hard gates and blockers

- Do not include secrets, private credentials, identifiable customer data,
  licensed manuscripts or private research files on the **public Saeit**
  repository/feature branch. A private-repo lane needs an authorized
  independently secured receipt adapter and must remain *unverified* in this
  shared Git receipt ledger until then.
- Source changes may count toward independently completed engineering work;
  they are **not** live deployment, customer delivery, collected payment or
  publication. Those each need separate authorized independent proof.
- Don't claim 50/50 for a technical quality-test dataset: temporary synthetic
  files only demonstrate correctness of the counter, not business progress.
- Never trigger bills, purchases, real trades, outbound email, ticket
  submission, customer-facing publication, irreversible deletion or
  production deployment without the required case-specific owner approval.
  Avoid Remote Desktop Commander and the retired PICM system.
- GitHub-hosted CI quality checks are not the persistent cycle runner.
  The hourly ChatGPT automations retain their existing schedules; the
  self-hosted worker's real availability and end-to-end execution must
  still be confirmed, not inferred from the presence of its workflow.

## Current execution gap

A–E task schedules exist, but the currently staged queues comprise only 96
`delivery_pending` records (A=50, B=6, C=10, D=20, E=10).
These are **not** success receipts. This bridge provides a validated handoff
path; it does not autonomously create 250 independent items or confirm
250 hourly executions. The next verified milestone is a committed genuine
per-lane receipt and a successful end-to-end central audit.
