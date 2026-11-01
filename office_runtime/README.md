# Zomorod private-office sidecar

Production deployment design for the separately registered cPanel/CloudLinux
Python application under the `/company/office/` base URI.

- CloudLinux root startup file: `office_passenger_wsgi.py` (`application`).
- Isolated Python WSGI entry: `office_runtime.passenger_wsgi:application`.
- A strictly validated temporary preflight mount can be selected via `ZM_OFFICE_BASE_PATH`; production defaults to `/company/office`. A separate `/office-preflight-<12 lowercase hex>/` is also supported to avoid inheriting the disabled Passenger rule of the existing `/company/` PHP directory. It is *not* a production cutover and requires independent selector registration, a separate SQLite DB, MFA, rollback and HTTPS acceptance.
- Isolated URLConf: `office_runtime.urls`.
- Explicit database: `/home/zomorod2/.private/zomorod-company-office/office.sqlite3`.
- Secrets remain only in the private app root's `.env` (mode 0600).
- No default outbound delivery or marketing publication.
- The existing PHP `/business/` accounting SQLite and public-site WSGI
  remain entirely separate. Never merge their DBs.
- Application registration, live base URI ownership, TLS, authorized MFA
  enrollment and reversibility must be independently verified **before**
  the sidecar is made public.

Creating these files does not register, enable, restart or publish an app.
