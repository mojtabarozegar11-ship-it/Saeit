# MOJ PROP staging release package

This package is for the English-only MOJ PROP staging cutover. It contains no
credentials and must not be copied over the live application without an
independent release review.

## Release order

1. Publish the tested GitHub main release through the cPanel release checkout.
2. Confirm the release checkout is the source used by Passenger; do not use an
   old extracted folder or a stale branch.
3. Provision or identify a physically dedicated MariaDB database for the five
   simulation tables.
4. Add the real database URL and identity digest secret through the staging
   secret store only.
5. Set MPW_MOJPROP_RECONCILIATION_SOURCE_ALIAS to the verified source alias.
6. Run the configuration-only preflight. It must report no blockers.
7. Run migration 0011_simulation_isolation only with the migration administrator.
8. Verify exactly the five isolated tables and no auth_user or factory relation.
9. Verify the runtime database user has only the approved runtime privileges.
10. Keep public route, invoice, KYC, and payment flags false during the canary.
11. Run an English-only health and login/reconciliation canary.
12. Enable public commerce only after a separate owner-authorized release gate.

## Hard stop conditions

Stop if the checkout is not a Git worktree, if the cPanel task points to a
nonexistent absolute path, if the target database is not physically separate,
if any secret is absent, or if any public payment flag is true before canary
verification.

The current host audit found each of the first two release-path defects in the
old staging checkout; this package is intended to prevent their recurrence.
