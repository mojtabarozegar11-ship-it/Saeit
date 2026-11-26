# MojProp.top direct-host release runbook

## Purpose

This is the only approved release contract for MojProp.top. It does not use the
legacy MojPlayWin document root, public URL, invoice host or deployment workflow.

## Required target

The release target must be supplied explicitly as MOJPROP_DOCROOT and its final
directory name must be mojprop.top or www.mojprop.top. Any path containing
mojplaywin is rejected.

## Mandatory evidence before any write

- MOJPROP_FULL_DB_APP_MEDIA_RESTORE_VERIFIED=true
- MOJPROP_TENANT_ISOLATION_VERIFIED=true
- MOJPROP_ROLLBACK_VERIFIED=true
- MOJPROP_RELEASE_APPROVED=true

The preflight script is scripts/mojprop_standalone_release_contract.py.
With no environment configured it must remain blocked. The script never deploys,
migrates, restarts Passenger or enables payment.

## Release sequence

1. Verify the dedicated cPanel document root for mojprop.top.
2. Verify HTTPS and host routing for mojprop.top.
3. Restore the MojProp database in isolated MariaDB without network.
4. Restore delivery files into the MojProp-only storage root.
5. Run tenant cross-read and cross-write denial checks.
6. Run an independent rollback rehearsal.
7. Stage the approved source package under the MojProp document root.
8. Compare every staged file with the approved Git SHA.
9. Restart only the MojProp Passenger application.
10. Verify homepage, catalog, contact, Starter30 and signal pages on mojprop.top.
11. Verify no public response contains mojplaywin.com, MojPlayWin or a legacy checkout URL.
12. Keep payment closed until the Starter30 no-transfer canary and settlement evidence pass.
13. Record the release manifest and live response hashes in the private office.
14. Only then consider opening the paid invoice gate.

## Current state

- Direct MojProp document-root evidence: absent.
- Independent restore/rollback evidence: absent.
- Payment: closed.
- Live page: still old content until this runbook is executed by an authorized
  deployment path.
