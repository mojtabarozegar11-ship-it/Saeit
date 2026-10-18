# MojPlayWin factory showcase — stage 2: internal manufacturing order bank

**Scope:** main mojplaywin.com only. Other site hosts, sub-sites,
cPanel live databases, the VPS factory, payments, consumer orders and
public storefront remain untouched by this code change.

The stage-1 intake proposal is PR #497. This follow-up PR #500 targets main for full CI, while retaining stage-1 commits until PR #497 merges; it does not deploy either phase.

## New isolated Django models

- \`MojPlayWinOpportunitySignal\`: durable source snapshot, deduplicated by
  \`venture:<slug>:<card>\`, \`section:<slug>:<card>\` or \`feature:<number>\`.
  All original site cards are represented; these are **content opportunities**,
  not proven consumer demand.
- \`MojPlayWinManufacturingOrder\`: internal **proposed** production brief
  from the 24 reviewed venture cards, one per source signal. Stores format,
  deliverable, provisional priority, owner candidate and review notes.
  Does not create \`core.Order\`, \`Product\`, \`AgentTask\`, payment or artifact.
- The sole allowed review statuses are \`proposed_for_review\`, \`scoped\`,
  \`rejected\`. There is no dispatch, approval, publish or payment status.
  Marking \`scoped\` requires a recorded reviewer note and responsible owner.

## Apply only in a confirmed, backed-up and migrated staging environment

\`\`\`bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test core.tests.test_mojplaywin_production_intake core.tests.test_mojplaywin_production_bank
python manage.py mojplaywin_sync_production_bank
\`\`\`

**After** verifying which database is actually used by the main MojPlayWin
Django admin (and taking a tested DB backup), a separately authorized
operator can apply the new isolated migration and seed the records:

\`\`\`bash
python manage.py migrate core 0040
python manage.py mojplaywin_sync_production_bank --apply --site mojplaywin.com
\`\`\`

No migration or \`--apply\` is performed by the PR or CI itself against
production databases. The sync is atomic, idempotent, create-only, and
preserves reviewer changes on reruns.

## Admin

Main-site superusers see two new Django admin lists only when the request
host is \`mojplaywin.com\` or \`www.mojplaywin.com\`.

- Activity signals: read original card title/description and add review notes.
- Internal manufacturing briefs: see source card, suggested output and
  priority; assign prospective owner, add notes, set \`scoped\` or \`rejected\`.

All fields that could imply evidence verification are **read-only false**
in this stage. New/delete through the admin are disabled. Other domain
hosts cannot access these two admin modules.

## Still NOT live / stage 3

Before the bank is promoted to factory execution:
1. Determine actual customer demand and validate the deliverable's value.
2. Verify genuine owner provenance and IP/license for each brief.
3. Add explicit owner-approved \`approved\` transition with a bounded,
   authenticated, idempotent VPS handoff, telemetry and cancellation.
4. Independently test produced artifacts, packaging and usability.
5. Connect only releasable products to storefront DB, active checkout
   and verified payment/delivery. Never fabricate a sale.

**Known blocking issue:** Zomorod site's environment has previously shown
an empty SQLite database; do not use that environment for migrations, this
MojPlayWin bank or public publishing. Production host mapping is a
precondition, not an assumption.
