# Zomorod Melal ERP — V7 offline release candidate

This version adds database-level invariants to the agricultural/industry record subsystem:
- Disallow direct SQL creation of already-released production batches or verified laboratory records.
- Disallow SQL direct status jumps or rewrites of source/identity fields.
- Require distinct reviewer identifier, HTTPS evidence and explanation for laboratory verification and batch release.
- Disallow deletion of industry records and changes to their append-only event log.
- Reject retirement of a land plot with a planned or growing crop, both from PHP and via SQLite.

**Important:** these SQLite controls do not establish the real-world identity, licensure or role of a reviewer who has unrestricted database access, and cannot substitute for external audit.

The offline runner reports each PHP+SQLite suite as PASS, FAIL or NOT_RUN. GitHub CI must execute all eight actual PHP behavioral suites on PHP 8.2 and 8.3.
No private production DB, SSH key, password, payment credential, scheduled job or live production code is included or changed.
Statutory tax, payroll, ERP, manufacturing, laboratory instrumentation and master-agent work remains incomplete. Do not label this full company ERP as 100% completed.
