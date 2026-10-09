# MojPlayWin deployment blocker: SQLite database location

## Evidence from authorized host checks (2026-10-09)
- Public domain uses `/home/zomorod2/mojplaywin.com/passenger_wsgi.py` pointing at `/home/zomorod2/Saeit-staging`.
- Runtime Python reported 3.9.25.
- The `.env` file in `Saeit-staging` contains `DATABASE_URL` with **sqlite** scheme (secret/path intentionally not logged).
- `/home/zomorod2/Saeit-staging/db.sqlite3` was not found. **This does not mean the database is missing.** The URL can specify a different absolute path.
- Partial file backups exist under `/home/zomorod2/mojplaywin-release-20261009-200458`: `live-wrapper.tgz`, `app-code.tgz`. No database backup was produced.
- Both authorized Remote Desktop Commander phases were consumed; no further remote access until renewed authorization.
- Production deployment was **not** attempted. Factory VPS unchanged.

## Safe resolution plan (next explicitly authorized maintenance window)
1. Use the actual configured Django runtime and settings to inspect `django.db.connections['default'].settings_dict['NAME']` locally. Log only the existence, file type and resolved directory; avoid publishing secrets or entire `.env`.
2. Verify the database exists and is SQLite; check filesystem ownership, permissions and free space. Do not create a new database or run migrations if it does not exist.
3. Back up using Python's `sqlite3.Connection.backup()` to a protected, non-web-accessible path, while preserving consistency. Do not rely on copying an active SQLite WAL file by itself.
4. Open the backup read-only and run `PRAGMA integrity_check`; require `ok`. Also record the original database file size and a checksum of the **backup**.
5. Verify the original active site's current configuration, templates and routes against the isolated PR. Preserve active site functionality and host routing.
6. Stage the exact PR commit with a separate WSGI/runtime and database copy; run system checks and URL smoke tests, then verify rollback by switching to the saved wrapper and database snapshot.
7. Only after all gates pass, deploy via an atomic switch, retain rollback files, and verify 41 pages and site health. Require owner-approved maintenance window if downtime or destructive migration is needed.

## Current release gate
**HOLD — database path, consistent backup and staging runtime are not verified.** Passing GitHub CI is not a substitute for production evidence. Do not merge, deploy, or change the factory VPS solely on the basis of this document.
