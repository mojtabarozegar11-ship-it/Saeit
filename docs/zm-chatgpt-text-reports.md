# Private ChatGPT work reports — Zomorod Melal

The private route is `/company/office/chatgpt-reports/` (CEO/superuser only, HTTPS and office MFA gate).
A distinct immutable `ChatGPTActionReport` holds report number, cycle, source run reference,
execution time, plain-text details, declared outcome, evidence URL and human review state.
Rendered text is HTML-escaped; unrelated assistant drafts and journal entries are never
misrepresented as ChatGPT actions.

**Intake:** Only an authenticated superuser can add a record through the private Django
admin. Use one numbered receipt per actual cycle delta; cite a concrete Saeit commit, PR,
issue, or GitHub Actions run. A record is not proof of real sales or production deployment.
Human evidence review is explicit. Duplicated report codes are rejected; records are
append-only. Corrections require a distinct, cross-referenced report, not an overwrite.

**Current integration boundary:** The ChatGPT hourly automation is separate from the
Django server. This patch does NOT claim to import full ChatGPT conversations, monitor
the background automation, or automatically ingest text from GitHub. Until an authenticated,
authorized reporting bridge is provisioned, the page honestly shows only records
actually entered in the private database. Do not store customer, bank or auth secrets
in public GitHub issues or Action logs.

**Release gate:** These changes are prepared on a feature branch. The current PHP
financial ledger remains authoritative. No production migration/merge/deploy is allowed
until independent off-host restore, effective Passenger DB identity, live MFA/roles
and rollback are confirmed.
