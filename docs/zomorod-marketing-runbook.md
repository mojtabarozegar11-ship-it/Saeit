# Zomorod Melal private marketing and domestic messaging runbook

Scope: **only** the internal desk of zomorodmelal.ir. This PR does not deploy, send a message, buy an ad, change existing public page layout, touch MojPlayWin, or alter factory VPS.

## Routes and operations
- Private office login: `/company/office/login/`; messaging inbox: `/company/office/messages/`.
- Campaign and publication desk: `/company/office/marketing/`, creation/approval routed through staff-only views.
- Registered platforms: Bale, Eitaa, Rubika, Soroush Plus, Gap, iGap, Telegram, Instagram, Facebook, LinkedIn, YouTube and owned website.
- Outbound per-contact bot messaging: Bale, Eitaa (Eitaayar app), Rubika; requires consent evidence and contact channel ID.
- Only validated automated **company channel publication** contracts: Bale, Rubika, Telegram. Eitaa and other channels are planning/manual publication records until official channel-post contract is independently verified.
- Provider response `accepted` means provider API accepted the request, **not** that human recipient received/read or an advertisement was shown.
- A campaign budget is a ceiling for planning, not spending authorization. No advertising purchase endpoint exists.
- Analytics and sales use explicitly recorded evidence references, never fabricated platform performance or unverified purchases.

## Fail-closed switches (all default OFF)
```text
COMPANY_MESSAGING_SEND_ENABLED=false
COMPANY_MESSAGING_BALE_ENABLED=false
COMPANY_MESSAGING_EITAA_ENABLED=false
COMPANY_MESSAGING_RUBIKA_ENABLED=false
COMPANY_MESSAGING_TELEGRAM_ENABLED=false
COMPANY_MARKETING_PUBLISH_ENABLED=false
```
Tokens configured as cPanel environment secrets, **not GitHub files**: `COMPANY_BALE_BOT_TOKEN`, `COMPANY_EITAA_APP_TOKEN`, `COMPANY_RUBIKA_BOT_TOKEN`, `COMPANY_TELEGRAM_BOT_TOKEN`.

Manual offline preview: `python manage.py dispatch_company_publications`; explicit execution after independent release approval: `python manage.py dispatch_company_publications --commit --limit 10`. The worker/cron is **not installed or enabled** by this PR. Ambiguous outcomes remain `uncertain` and are never retried blindly.

## Release checks before **any** production deployment
1. Back up and verify restore of the effective Passenger/MariaDB database and application; ensure disk space and reverse proxy health.
2. Inspect live authenticated `/company/office/login/` and permissions. Fix any previous 503/timeout; do not publish private admin UI publicly.
3. Run `python manage.py check --deploy`, `python manage.py makemigrations --check --dry-run`, `python manage.py migrate --plan`, audit migrations on **staging only**, and run company marketing/messaging + ERP regressions.
4. Register channels **actually controlled by Zomorod Melal**, document ownership evidence, opt-in/out and legal rights to ad copy, assign staff roles and review audit log.
5. Configure provider credentials in secrets storage; obtain provider acceptance contract and posting permissions; confirm official API quotas and local advertising rules. Do not collect bot passwords in the web panel.
6. Deploy via pre-existing GitHub Actions → VPS relay → cPanel path with constrained scope, restore-tested rollback, then verify private pages, public-site unchanged.
7. Only after all above and separate authorization for sending, enable relevant channel switches and private worker. Do not schedule paid ads without independent spending approval.

Known environment risk at code authoring: live `/company/office/messages/` was 404 while private login could not be verified, so **this PR is CODE ONLY, not a running live service**.
