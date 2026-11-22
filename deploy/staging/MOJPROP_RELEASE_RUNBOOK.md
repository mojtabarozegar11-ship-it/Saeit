# MOJ PROP controlled release runbook

This runbook is for the English-only MOJ PROP release candidate. It contains no
credentials and must not be copied over the live application without an
independent release review.

## Current candidate state

- Candidate branch: `ops/mojprop-simulation-stage-ledger-20261122`
- Candidate feature: isolated simulated stage ledger and read-only buyer display
- Expected terminal migration for this candidate: `0008_simulation_stage_transition`
- Production deployment: not performed
- Public payment: must remain closed until the release gates below pass
- Live application is known to be older than this candidate; do not infer parity
  from HTTP 200 responses.

## Release order

1. Record the exact candidate commit SHA and verify all required CI checks are
   successful.
2. Create or identify a clean cPanel release checkout that is a Git worktree
   for the verified candidate. Never use the old extracted
   `Saeit-mojplaywin-integrated-20261119` directory as a release source.
3. Confirm Passenger/LSWSGI points to that exact checkout and record the
   parent/worker process state without restarting the global service.
4. Create and verify a recoverable application backup and a dedicated database
   backup before any schema operation.
5. Provision or identify a physically separate MariaDB database for the
   isolated MOJ PROP domain. It must not be the factory database, the default
   commerce database, or `auth_user`.
6. Configure the database alias and identity-digest secret through the protected
   secret store only. Never commit credentials.
7. Run configuration-only preflight and save its machine-readable receipt.
   The preflight must report no blockers.
8. Run the migration plan only:
   `python manage.py migrate prop_firm --database=mojprop --plan`
   Save the plan and confirm that the candidate includes
   `0008_simulation_stage_transition`. Do not apply it during preflight.
9. Obtain a separate migration-admin approval, then apply only the reviewed
   plan. This step is outside the current source-only PR.
10. Verify the applied migration state and approved isolated tables. Verify that
    no model relation reaches `auth_user`, the factory database, broker
    execution, wallet custody, or treasury settlement.
11. Verify the runtime database user has only the approved runtime privileges.
12. Keep public route, invoice, KYC, email, payment, payout and crypto-execution
    flags false during the canary.
13. Run an English-only health, login, read-only buyer-portal and reconciliation
    canary. No customer record or payment may be fabricated.
14. Enable public commerce only after a separate owner-authorized release gate,
    successful rollback rehearsal, and an observed clean canary.

## Hard-stop conditions

Stop immediately if:

- the checkout is not a Git worktree or its SHA is unknown;
- Passenger points to an old extracted directory;
- the target database is not physically separate;
- backup or rollback evidence is missing;
- migration plan differs from the reviewed candidate;
- any secret is absent or exposed;
- any public payment, payout, email or crypto flag is true before canary;
- any worker restart would require restarting unrelated sites;
- the live database contains unexpected customer or payment rows.

## Rollback principle

Rollback means restoring the verified application backup and reverting the
application release through the controlled checkout. Never reverse a production
migration by deleting tables or records. A schema rollback requires a separately
reviewed database procedure and backup restore.

This runbook supersedes the older document that referenced
`0011_simulation_isolation`; that migration name must not be used for this
candidate.
