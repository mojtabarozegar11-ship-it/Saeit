# MOJ PROP — organic Facebook educational funnel into Starter30

**Release date:** 2026-11-21. **Live production scope:** three English MOJ PROP education pages only and one shared JavaScript asset. Everything was published atomically on cPanel after private SHA-pinned backup, and independently fetched over public HTTPS. GitHub source mirrors the **exact** already-live bytes.

## Why this matters

A newly scheduled organic Facebook educational campaign links first to English MOJ PROP risk management, drawdown and simulated-versus-live guides. Those public articles link readers into the official 30 TRX Starter30 product page, but their existing plain internal links dropped `utm_source`, `utm_medium`, `utm_campaign` and `utm_content`. The separate product-page-to-checkout source PR #2825 had already been merged (GitHub SHA `908b9348da32ea3eb00caa6c79dea7e59db1d581`), but no end-to-end attribution existed for the guide → product transition. This is a campaign source attribution defect, not proof of visitor or revenue.

## Safe actual fix

- Exact live pages:
  - `/moj-prop/education/risk-management/`
  - `/moj-prop/education/drawdown-and-position-sizing/`
  - `/moj-prop/education/simulated-versus-live/`
- Only one external `<script defer src="/moj-prop/education/campaign-attribution.js"></script>` tag was added to each already-indexed English HTML file.
- One new same-site `/moj-prop/education/campaign-attribution.js` uses **only** four vetted campaign tags, accepting values of at most 80 characters matching ASCII campaign-safe regex, and rewrites **only same-origin approved public educational navigation links** to Starter30 information, English MOJ PROP home, rules and public education paths.
- It never redirects, sends network requests, touches the payment/checkout path, or collects wallet/email/identity/session, cookies or arbitrary query string parameters; it never modifies outside-domain links, site payment or recruitment pages. Ordinary links still work if JavaScript is disabled.
- Source files mirrored under `templates/moj-prop/education/`; independent targeted tests exercise the real JS in Node VM. No app WSGI, Django, DB, TRON payment, campaign spending, cron or factory changes.

## Hashes and rollback

Private cPanel backup:
`/home/zomorod2/separated-backups/20261121/mojprop-education-utm-funnel/` including three exact HTML originals (permissions 0600), `manifest.json` (0600) and per-file SHA hashes. Rollback must be scoped to these three original files plus the one new JS, only after comparing current files to the verified post-change SHA, and must use atomic replacement; never run broad deployment.

| Asset | SHA-256 before | SHA-256 published |
|---|---|---|
| risk-management/index.html | `3c102910896903571f18060a83f437aa8979bae22038734816b00018c5dd15c5` | `be6f53906c5c745a56f3f72aad244baed0c046391214a820570c846feed4bae3` |
| drawdown-and-position-sizing/index.html | `9c6f335dc905d27843366ea7c687d4e83c91197d52f7d7f0b9bf72f51cba24d1` | `6c914f0fc36ea9f446300bbbf4b527503b0d7a178635fe9ef4107a01105fb3b7` |
| simulated-versus-live/index.html | `2cc6571185ce32481e029dda940159d9930688348ea10a3fca9cedae358438d6` | `76a38c51c0b72b198fec1d6f38e8795e2f623476f6a0f2c51acf710967e7c95b` |
| campaign-attribution.js | absent | `f05a90b9436e9d17669735e6939083f023c56b7662158a6d869d1f08a3a1d52e` |

All **four** public URL responses were HTTPS 200 with exact host-file equality; Node JS `--check` passed, allowed-path behavior VM passed. At pinned source commit `9541e36cbdc609321fe19dd5230b38218a66b2d0`, all four tracked source artifacts were **byte-identical** to the live host, and `3` targeted Python tests passed (including real Node.js DOM simulation).

## Business truth

This is free organic marketing attribution with no cookies and no payments. A `begin_checkout` telemetry event can be triggered by automated page GET and is not proof of an individual human buyer. Actual invoice/payment counts must be taken only from the dedicated production MOJ PROP database or verified TRON settlement; at the last audit these remained zero. Metricool scheduled posts remain `PENDING` until an actual publication receipt is observed. Search engine indexing, unique visitors and sales are not established by this fix.
