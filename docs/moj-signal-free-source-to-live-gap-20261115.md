# Mojtaba.bot.ai free-signal enrollment — live production gap (15 November 2026)

Operational identity: `mojtaba.bot.ai` is **one bot**. The customer-accessible front end is MojPlayWin until actual parent-domain DNS rights and TLS are verified.

## Verified starting evidence
- PR #2407 merged the freely readable historical educational methodology and branded paid inquiry funnel.
- PR #2428 merged email double-opt-in and private subscriber lifecycle into GitHub `main` at `02c7195623f54b76b4033f1c7d14309ae1432ba9`.
- Public read-only GitHub Actions from 2026-11-15 18:21 UTC: HTTPS GET to `/moj-prop/`, `/moj-prop/catalog/`, `/moj-prop-intake/`, `/moj-prop/signals/` returned HTTP 200; Moj Prop intake returned valid CSRF JSON; `mojtaba.bot.ai` failed DNS with Google+Cloudflare both NXDOMAIN. **No buyer registration, email or payment was performed.**
- That earlier probe did not check the **new** root `/moj-signal-free-subscribe/` endpoint or membership form marker; it was insufficient to declare free enrollment live.

## Exact-source installer fix
The static catalog installer previously accepted only the very old Signal Desk baseline; legitimate live page version from merged PR #2407 could be rejected as "unknown change". It now recognizes three, and only three, exact approved states:
1. Original pre-#2407 file, preserved at `templates/moj-prop-v4/baselines/signals-index-before-free.html`.
2. Exact #2407 open-access free-preview file, preserved as `baselines/signals-index-after-free-preview.html`.
3. New approved free double-opt-in file `templates/moj-prop-v4/signals/index.html`.

All unknown live changes still cause **fail-closed** refusal, and the exact previous bytes are saved in the checksum-guarded backup manifest for rollback. No overwrite of a merchant-customized site.

## Public read-only evidence gate
`.github/workflows/mojprop-public-readonly-24h-evidence-20261115.yml` now probes these URLs with **GET only** and no credentials:
- Moj Prop landing, catalog, existing intake and Signal Desk.
- New `/moj-signal-free-subscribe/` root WSGI endpoint. It checks that the public JSON has `ok:true`, `agent=mojtaba.bot.ai`, expected product, a CSRF token (never prints its value), an explicit `enabled` boolean and `paid_entitlement:false`.
- Representative financial brand and Arabic brand paths, and independent DNS for the bot host.
- HTML markers of public open sample and the separate optional email checkbox form.

It reports `PUBLIC_SIGNAL_FREE_API_CONTRACT=valid/invalid`, `PUBLIC_SIGNAL_FREE_OPTIN_FORM=yes/no`, `PUBLIC_SIGNAL_FREE_EMAIL_FLAG=disabled/enabled-config-only/unknown` and separately `PUBLIC_MOJPLAYWIN_HOST_ROUTE_GATE`. No live POST is sent. A successful Actions job is merely a **completed observation**, not proof of a healthy or commercially ready site.

## Manual go/no-go release (no implicit authorization)
1. Check HEAD, latest CI, the full release workflow and independent database/media backup **and restored copy**; verify tenant isolation and a documented rollback drill. Three GitHub variable attestations must reflect actual evidence, not be set just to bypass gates.
2. Run the explicitly authorized backend migration through controlled `0046_signal_free_subscription`, preserve site-specific owner files, then release static page from one of the exact reviewed baselines. No push-to-main auto-deployment, no unrelated database migration.
3. Verify live GET of new API, consent UI and support traffic; `enabled=false` is expected while SMTP proof is missing.
4. Verify sender domain ownership, SSL/TLS, SMTP authentication, verified sender identity, opt-in privacy notice, authenticated consent with a willing real email recipient, and unsubscribe POST. Only then separately approve and set `MOJTABA_SIGNAL_FREE_SIGNUP_ENABLED=true`.
5. Provide one independently reviewed original historical educational example with dated provenance; do not misrepresent actionable entry/exit signals as licensed/advised investments.
6. Paid reports remain **manual quote only** until lawful TRON recipient, source identity, independent payment finality, invoices/refunds and actual deliverable-to-customer evidence are verified.

## Accounting rule
A GitHub merge, public page HTTP 200, opt-in request, or unissued price card is **not** a sale. Count verified free members only after successful confirmation POST recorded in persistent DB. Count cash sales only with payment settlement evidence plus delivered paid entitlement. Otherwise status is `unknown/unverified`, not fabricated revenue.

**This change deploys nothing, sends no real email, spends nothing and performs no trade.**
