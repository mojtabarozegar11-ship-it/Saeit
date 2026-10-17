# Zomorod Melal — Live Passenger 503 recovery and release gate

**Status:** BLOCKED — do not merge or publish PR #400.  
**Scope:** only the primary `zomorodmelal.ir` Django/Passenger application.  
**Historical content reference:** 2026-10-14 01:00 Asia/Tehran (2026-10-13 21:30 UTC). The exact full-site/data/media backup is **not verified**; timestamps of individual files are not proof of a complete snapshot.

## Verified evidence (17 October 2026)

| Check | Production | Staging |
|---|---|---|
| Public `/api/health/` | HTTP 503 | HTTP 200 |
| Public `/admin/login/` | HTTP 503 | HTTP 200 |
| Public `/agents/` | HTTP 503 | HTTP 200 |
| Internal Django test client `/api/health/` | HTTP 200 | — |
| Internal Django test client `/admin/login/` | HTTP 200 | — |
| Internal Django test client `/agents/` after original CSS repair | HTTP 200 | — |

- Main web app startup logs during *new* requests reference `/usr/local/lsws/fcgi-bin/lswsgi_wrapper` line 9 and the nonexistent `/bin/set_env_vars.py`. The wrapper takes `VIRTUAL_ENV` (or falls back to `PYTHONHOME`); the effective environment is not being passed through correctly. **Investigate LiteSpeed/CloudLinux bridge, not page content.**
- Staging is available but its database and state are not interchangeable with production.
- Verified original `site/emerald-system.css` restored transactionally into production Django static source, staticfiles and manifest. SHA-256: `efeb49358d01f93bad576aff9db89f1400a9ea734a1240be86831f026481aeb4`; 3,480 bytes. Authentic source is preserved in this PR at `core/static/site/emerald-system.css`.
- CloudLinux Selector app URI `''` → `'/'` did **not** resolve HTTP 503; run 39003553947. Original empty URI and hashes were successfully restored in run 39003687733.
- Previous lazy WSGI, `PYTHONHOME`, and `PassengerPython` canaries also failed HTTP tests and were reverted. Do not retry them unmodified.
- Read-only diagnostics: GitHub Actions 39004008432 (10/10 regression tests), plus action 39002916386 showing fresh `set_env_vars.py` messages.
- Source history indicates original company content in `core/views.py`; both About and Company changes are additive and covered by preservation checks.

## Server-administrator-only repair

**Do not run in a shared cPanel shell without root/WHM privileges.** The LiteSpeed wrapper and module configuration are server-owned; the required fix can affect other server accounts. The provider's authorized server administrator should:

1. Create and verify **host-level** backups of LiteSpeed/CloudLinux configuration and current production `.htaccess`, app environment and data. Obtain rollback procedure and a maintenance window. Do not overwrite website content or production DB.
2. Verify loaded LiteSpeed version, CloudLinux Python Selector support and the availability of `alt-python310-wsgi-lsapi`. Inspect why the LiteSpeed application launch environment fails to provide `VIRTUAL_ENV`/`PYTHONHOME` while the same app runs in a Python shell.
3. Follow the official cPanel/LiteSpeed CloudLinux integration procedure. **Root-only, after backup:**
   ```bash
   /usr/local/lsws/admin/misc/enable_ruby_python_selector.sh
   ```
   This installs/configures required Ruby/Python LSAPI integration; it is a server-wide action, **not a guaranteed fix**, and must be supervised by the host. CloudLinux may separately require the appropriate `alt-python310-wsgi-lsapi` package.
4. Recheck `/api/health/`, `/admin/login/`, `/agents/`, `/contact/`, `/economy/`, `/market/` and other dynamic routes for HTTP 200. Check authenticated actions via a safe test identity only. Review the *new* LiteSpeed/Passenger logs, not stale tracebacks.
5. Confirm every previously working page remains unchanged and HTTP 200: `/`, `/about/`, `/company/`, `/mohammad/`, `/ghanadi/`, `/amozeshgah/`. Compare file SHA-256 fingerprints, as well as database and media counts. Abort/rollback on any regression.
6. Only after production is healthy, verify the historic 14 Oct snapshot, apply **additive** corporate copy recovery, and test unique editorial images and mobile usability. All original URLs, SEO, forms, data, admin functions, local agents and payment flows must remain intact. No 100/100 until full acceptance evidence is recorded.

### Official references
- cPanel, Ruby/Passenger/Python 503 on LiteSpeed: https://support.cpanel.net/hc/en-us/articles/4409877232279-Ruby-Passenger-Python-applications-503-on-LiteSpeed
- cPanel, Python Selector and LiteSpeed: https://support.cpanel.net/hc/en-us/articles/360051851034-Why-does-my-python-application-created-with-CloudLinux-Python-Selector-show-a-503-error-when-using-LiteSpeed
- LiteSpeed CloudLinux integration: https://docs.litespeedtech.com/lsws/cp/cpanel/cloudlinux/
- CloudLinux, missing Python 3.10 WSGI-LSAPI package: https://cloudlinux.zendesk.com/hc/en-us/articles/5913550611740-alt-pythonXXX-wsgi-lsapi-missing

## Non-negotiable acceptance

Zero removed pages, content, URLs or independent websites. No repeated editorial photos. Zero failing critical routes. Verified rollback. Full original and live content parity. WCAG 2.2 AA and responsive/mobile checks. Accurate 100/100 only after evidence across the *entire* main site, not just successful CI.
