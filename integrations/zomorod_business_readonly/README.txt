Zomorod management bridge — S-01 isolated draft

STATUS: CODE ONLY; NO LIVE API, NO DEPLOYMENT, NO CREDENTIALS. This draft adds a fail-closed WSGI factory, not an installed web application. It never imports the mutable site PHP app, touches the factory, creates a cron, or writes to accounting.

Verified repository baseline: content/zomorod-business/index.php loads a private host-only app; its accounting database is ~/.private/zomorod-business/management.sqlite3. Live host app.php has independent extensions not fully represented in GitHub; never replace it wholesale. PR #1573 reported a private command center but no ChatGPT connector. PR #1678 contains staged V7 candidate only.

For S-01 after explicit review: deploy a separate, authenticated HTTPS WSGI mount with a dedicated service identity, verified origin REMOTE_ADDR, pinned gateway egress IP and least privilege; never expose this bridge directly to the public before identity/authorization, rollback, audit logging and secret rotation gates. The bridge requires ZM_RO_BRIDGE_DB (absolute private path), ZM_RO_BRIDGE_TOKEN_SHA256 (SHA-256 of a new strong independently revocable token), ZM_RO_BRIDGE_ALLOWED_IPS (approved CIDR), DOCUMENT_ROOT (actual public root). No token, hash, project data, finance totals, or export may be stored in this public repository, PR, logs, or public Actions artifacts. A separate ChatGPT connector/agent must be authorized and securely configured; merely adding this draft does not connect ChatGPT.

Authorized GET endpoints: /v1/health, /v1/projects?limit=50, /v1/finance-summary, /v1/inventory?limit=50. Limits 1–100; stored integer money is not profit and is never converted. SQLite opens with mode=ro, query_only=ON; no writes. Unconfigured, unallowlisted, non-HTTPS or missing-token access fails closed. All data responses are private and no-store. Validate live schema and trusted reverse proxy separately.

Offline QA: from repository root run python3 -m unittest integrations.zomorod_business_readonly.test_bridge -v . Only synthetic temporary SQLite is used. No production access is claimed. Existing factory and master-agent HOLD is unchanged.
