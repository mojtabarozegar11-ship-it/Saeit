# MojPlayWin sitemap release provenance — 2026-11-20

Scope: traceability only. This manifest records the currently active host-side sitemap endpoint and the source snapshot stored beside it. It is not a deployment instruction.

## Live host evidence
- PHP handler: `/home/zomorod2/mojplaywin.com/design-preview-20261017/_mpw_sitemap_three_indexable_20261017.php`
- PHP SHA-256 reported by host: `3d4e4d50348419e7a3bd08bd71276bf6fbe1e5b64b7768e8383fbcfa75321dcc`
- Domain `.htaccess`: `/home/zomorod2/mojplaywin.com/.htaccess`
- `.htaccess` SHA-256 reported by host: `57dfa57660113a64bd5057cf8e6a1f53152a62c11b72279fb800b4347013ed43`
- Active sitemap rewrite is GET-only, exact `/sitemap.xml`, excludes the passthrough query, and matches `mojplaywin.com` / `www.mojplaywin.com`.
- PHP low-count path requires a valid, unique, same-origin XML base and adds only the four Moj Prop subpages when the base has 4–19 URLs. It exits after that path. The pre-existing >=20 path remains separate.

## Repository snapshot
- The current host PHP text was read through the authorized remote read-only device path and added at `ops/cpanel/mojplaywin/sitemap/_mpw_sitemap_three_indexable_20261017.php`.
- The repository copy was compared to a fresh host read after update and matched character-for-character as returned by the text readers. A byte-for-byte comparison of host file bytes against Git blob bytes was not independently performed; the host SHA above is retained as the deployment baseline.
- The root `.htaccess` is not tracked at the corresponding path in Saeit. This manifest records its host hash and the exact sitemap condition semantics, but does not copy the entire site-wide rewrite configuration into the repository.
- Historical scripts such as `scripts/mpw_20261025b_sitemap_add.py` refer to the same live handler path.

## Change and release boundaries
- This branch adds a source snapshot and provenance document only.
- No production file was changed in this cycle.
- Do not deploy the snapshot automatically: first review its full content and compare host bytes, line endings and source ownership. Keep the existing private host backups and rollback instructions.
- No database, payment, signal, factory, email, unrelated host route, or expense was involved.
