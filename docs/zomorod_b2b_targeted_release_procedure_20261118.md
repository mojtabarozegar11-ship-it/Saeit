# Zomorod B2B: narrowly scoped create-only release gate (2026-11-18)

This is a genuine importable cPanel filesystem transaction tool; NO production workflow calls it and its CLI exposes ONLY a read-only preflight. Existing public site, Django application, database, cron and Faremah are excluded.

- Exact target: /home/zomorod2/public_html/b2b only, a **new** directory. Refuse existing directories, files and symlinks.
- Inputs: exact reviewed source tree containing public/b2b/index.html and public/b2b/privacy/index.html; reproducible no-deploy ZIP verifier; owner-specific release authorisation string.
- Install: private stage under owner home; checks source SHA256 against manifest; fsync files/directories; Linux renameat2 with RENAME_NOREPLACE (no overwrite fallback); verify exact created contents.
- Rollback: separate release-specific authorization; refuses unknown files or modified bytes; unlinks only verified created files and directories. It does not replace or touch prior content.
- NO source deletion, NO migration, NO application reload, NO payments, NO homepage or Faremah write. Static pages may still be shadowed by Apache/Passenger and require separate HTTP/HTTPS proof.
- The authorisation string is an operational explicit-approval gate, not a cryptographic signature or backup/restore proof. Do not invoke install from any automated PR job.
- Full-site database+application+media backup and isolated restore are STILL required for the separate Django B2B/CRM code release; they are not required merely to build a static-only ZIP.
- After a *separately owner-approved* create-only release, verify public GET of both paths, correct status, TLS, content SHA and no changes to preexisting public_html/index.html and public_html/faremah. If routes are shadowed or errors occur, use the separately gated byte-checked rollback only.
- No live deployment, backup or buyer conversion is claimed by this document.
