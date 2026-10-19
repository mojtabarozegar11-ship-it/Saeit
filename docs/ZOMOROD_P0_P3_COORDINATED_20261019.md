# Zomorod Melal — coordinated P0–P3 source patch, 2026-10-19

## Scope
Only the Zomorod site source, source-level security and the site-specific panel UI.
No independent cPanel document root, MojPlayWin configuration, /tala/, /mohammad/,
or /amozeshgah/ code is changed.

## Implemented in this branch
- P0: Make the site-local hourly eleven-agent monitor fail when one run fails, is missing or reports non-200, instead of reporting success after ten passing roles.
- P0/P2: Standalone bounded read-only GET check for nine public routes with a machine-readable report. No login, checkout, admin or POST requests.
- P1: Attach historical Django task counts and per-agent completion/failure chart (Zomorod-only) to the staff panel. Clearly distinguish records from unproven VPS or PHP health.
- P1: Resolve lib64 wheel lookup against the actual Passenger interpreter version and enforce secure session/CSRF cookie defaults in production without assuming global redirects are safe.
- P2/P3: Add regression tests, a narrowly scoped coordinated audit workflow and traceable results; leave legacy and independent subsite workflows untouched.

## Safety boundaries and blockers
- A failed agriculture PHP agent is now faithfully marked FAILED, but its runtime cause still requires private cPanel logs and application diagnosis. The monitor invokes the normal cycle only once to avoid duplicate work.
- External origin reachability, Passenger process health, DNS, live database consistency and updated TLS headers require independent live evidence.
- The private factory has proven package builds but product certification and cross-site publication are not enabled by this patch.
- All-site autonomous publishing without validated QA, rollback, ownership and per-site allowlisting is not safe.
- Source CI success is not proof of live deployment or 100/100 quality.

## Final production rollout gate
1. Confirm Django CI and the new read-only contract tests.
2. Snapshot live files and database, compare SHA-256 of independent subsite document roots, and record pre-release fingerprints.
3. Deploy ONLY separately verified Zomorod app files via established pinned GitHub Actions -> VPS -> cPanel pipeline.
4. Verify root HTTP, agent outcomes, DB-to-panel data, TLS, browser accessibility, cache and exact revision after release.
5. Roll back on any regression; do not delete old working pages.
