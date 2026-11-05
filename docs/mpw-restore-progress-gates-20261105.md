# MojPlayWin encrypted-backup isolated restore: timeout diagnostic

Current evidence (workflow run 41444903762, 2026-11-02): manifest-only
pair readiness passed, but the private SQL -> isolated MariaDB pipeline reached
the 5,500-second limit with source and consumer exit code 124. No completed
GPG stream integrity check or successful isolated SQL restore was recorded.
No release or backup recoverability claim follows from that run.

The owner-armed workflow now relays SQL through
`scripts/mpw_isolated_sql_progress_20261105.py` *between* the same pinned VPS
source and a network-disabled temporary MariaDB Docker container. The relay
copies the binary stream unchanged and emits only integer GiB milestones to
stderr; it never parses, saves or logs SQL rows, table names, credentials,
emails, paths or hashes. Its 48 GiB upper bound matches the source producer.

The workflow checks all three pipeline exit codes, classifies exit 124 as
`ISOLATED_IMPORT_TIMEOUT`, and still requires independent source GPG/SHA256
validation, a successful MariaDB import, nonempty restored schema/tables and
the subsequent private file-root restore. A relay EOF is **not** proof of any
of these requirements.

This commit changes GitHub source only. `workflow_dispatch` remains protected
by the existing owner/branch/confirmation gate; no action is scheduled by this
change, no backup is created, and no cPanel or live payment code is changed.
Another long restore is not justified solely to collect milestones: first
review encrypted manifest size, runner/VPS resource budgets, and an approved
restoration plan. The owner must separately approve the next expensive run.
