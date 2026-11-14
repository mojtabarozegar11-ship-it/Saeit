# 2026-11-14: actual Passenger UAPI registration does not establish Django checkout origin

Canonical bot: `mojtaba.bot.ai` (no new services, bots or paid dependencies).

## Production discrepancy — evidence, not an authorization
The owner-authorized read-only `passenger_inventory` workflow on the pinned GitHub Actions → VPS → cPanel route returned a sanitized UAPI record for `mojplaywin.com`. An independent source-level comparison to the cutover's assumed `/home/zomorod2/Saeit-staging` and public document root did **not** reproduce the registration's root fingerprint. The registration base URI was also not the explicit `/` URI (the existing sanitizer redacts its exact value). These findings identify a concrete source-ownership mismatch to investigate before any cutover. They do not prove the real served Django view, template or physical target path.

## Exact deliverables
1. `scripts/mpw_passenger_root_reconciliation_20261114.py` reads only the **redacted**, bounded output from the already established UAPI inventory sanitizer, not raw cPanel JSON, credentials, customer data, website content or database.
2. It independently computes the fixed SHA-256[:16] candidate root digests, checks domain and mapping cardinality, rejects duplicate/unredacted/oversized input, discloses only Boolean candidate matches and safe labels.
3. It cannot prove effective WSGI import, loaded Django template, schema migration, production CSP, POST checkout, TRX finality or paid entitlement. All remain false/unknown and release permitted is always false.
4. 40 regressions exercise real sanitizer compatibility, misleading non-root path, wrong root, conflicts, omissions, untrusted raw UAPI and confidential-path redaction.
5. This PR's GitHub workflow is unprivileged, source-only, and uses **synthetic** UAPI data. Fresh live evidence comes separately from the existing owner-approved `passenger_inventory` workflow on main; it is never embedded in a public commit.

## Next operational remediation (still not performed)
- Through a separately approved **read-only** cPanel source provenance operation, compare UAPI app-root registration, `.htaccess` Passenger root/base URI, literal WSGI assignment and allowed application directory fingerprint, without disclosing raw paths. Do not assume any source file is serving the public checkout simply because it exists.
- Independently attest Django's effective checkout template and the registration of the current buyer-email route and migration 0049, without creating a buyer order.
- Only then plan a recoverable, owner-approved deployment of the `script-src` header and dynamic store routing. Re-probe 10 public GET paths, test legitimate emails and independently settled paid deliveries in the authorized environment.

No edits to production cPanel/Passenger, no payment, no TRX wallet transfer, no outbound customer mail, no merge or DNS changes. Green source tests are not evidence of collected revenue.