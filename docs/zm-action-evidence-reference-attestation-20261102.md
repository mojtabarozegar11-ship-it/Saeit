# Zomorod cycle 05 — GitHub reference-checking boundary

Scope: `zomorodmelal.ir` only. Source branch PR #1793, **not a production release**.

`scripts/zm_chatgpt_evidence_verify.py` reads the separately maintained private
`chatgpt_actions_index.sqlite3` and checks at most 100 of the most recent
completed-status references against GitHub's fixed repository API. Its output
`chatgpt_evidence_attestations.json` is an independent, non-financial file.

Reference statuses are `source_exists`, `ci_success`, `ci_not_successful`,
`merged_source`, `proposal_only`, `issue_exists`, `mismatch`, `unavailable`,
`invalid_reference` or `not_checked`. These indicate only the state of the
linked GitHub object. **None** establishes that a claimed code change belongs
to the action, was deployed, produced a sale, settled at a bank, delivered to
a customer, or hired a worker.

## Safe execution

No production installation is included. Offline unit tests mock all web calls.
An operator who separately verifies the cPanel private runtime and grants a
bounded, read-only network route can preview the result with:

```sh
python3 scripts/zm_chatgpt_evidence_verify.py \
  --index /verified-private-dir/chatgpt_actions_index.sqlite3 \
  --output /verified-private-dir/chatgpt_evidence_attestations.json --limit 30
```

The command does not write its output without `--commit`. A future authorized
release may set `ZM_ACTION_EVIDENCE_VERIFY_ENABLED=1` on the trusted host and
use `--commit` after backup, exact source identity, role and rollback acceptance.
Do not put GitHub tokens in CLI arguments or public issues; the optional
read-only `ZM_GITHUB_REPORTS_READ_TOKEN` belongs only in server secrets.

The private output is created atomically with `0600` permissions under a
`0700` directory, with anti-symlink checks and protection of existing action
IDs and receipt hashes. A private report viewer can display source-reference
counts separately from its permanently **zero independently business-confirmed**
count. The checker has no import of business PHP, payment, bank, factory or
marketing modules and no path to financial SQLite.

## Missing acceptance evidence

- Full owner-key off-host recovery and rollback rehearsal.
- Actual staff MFA and role-based browser journeys.
- Confirmed operational Django database identity, distinct from PHP ledger.
- Live receipt/CI/reference correlation and separate deployment probe.
- Bank-settled payment and customer delivery evidence.
- Independent assessment of material economic impact, not only link existence.

Until these gates pass, do not claim autonomous management or release the
unified ERP from draft. Keep cycle 05 as the existing ChatGPT hourly controller.
