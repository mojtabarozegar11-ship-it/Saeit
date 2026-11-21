# English Starter30 landing-to-checkout attribution — production release

Date: 2026-11-21. Public entry: `https://mojplaywin.com/moj-prop/starter-30-trx/`. This change **was already narrowly published and verified on the cPanel host**, independent of any broad Django deployment.

## Root cause

The owner's six new organically scheduled Facebook promotional posts use campaign tags `utm_source`, `utm_medium`, `utm_campaign` and `utm_content`. The static English Starter30 product landing page linked to `/mojprop-starter30-checkout/` without forwarding the campaign. The separate live Django checkout already has source and hidden-field support for UTM on GET and POST, so dropping these tags before the checkout loses the original campaign attribution.

## Actual production action

- Edited **only** the static `/home/zomorod2/mojplaywin.com/moj-prop/starter-30-trx/index.html` to reference one external, local JavaScript file.
- Atomically created `/home/zomorod2/mojplaywin.com/moj-prop/starter-30-trx/checkout-attribution.js`.
- The script reads *only four allowed UTM keys* from the product page URL. Values must be at most 80 characters and match `[A-Za-z0-9_.:-]+`. It appends them to the official **same-origin exact checkout path** only, preserving already specified values and ignoring all other query keys.
- It never reads/submits identity, wallet, email, payment, invoice, receipt, session or cookie fields; makes **no network requests**; does not rewrite external links or any non-checkout link; and cannot prevent a checkout click if JavaScript is disabled.
- No Django, WSGI, TRX, wallet, payment configuration, database, other pages or factory changes.

## Evidence and rollback

Pre-change static HTML SHA256 `41227882ca5cecaf8877377cef3501491c5bb1f6e2297c05c5896dcaded253c9`.  
Post-change live HTML SHA256 `8ad2dfaa419b9518d7e3133c305e42f8632152249c8ce6050eb164b34d4e8842`.  
New live JS SHA256 `b38ba9e0e0c72a94565ade6484f22ab7cb082e06bf26f602bebb3f68ac418dba`.

Private backup and verified manifest:
`/home/zomorod2/separated-backups/20261121/mojprop-starter30-utm-checkout/`

Live HTTP checked: product page 200 with byte-for-byte host parity, script 200 with `text/javascript` and exact host bytes. `node --check` passed. Six browser-like Node VM cases passed: all four tags copied, none copied without tags, unknown email/wallet params ignored, unsafe value rejected, existing UTM kept, overlong value rejected.

Source `templates/moj-prop-v4/starter-30-trx/index.html` and `templates/moj-prop-v4/starter-30-trx/checkout-attribution.js` were verified at pinned commit `d9074281a25ad1baf99627dc95b6c6b50f15a5e8` **byte-for-byte identical** to the already live cPanel files. Targeted source tests: 3 passed (including six live-JavaScript VM scenarios).

Rollback: after confirming exact current SHA values, restore the separately backed-up original HTML and delete only the `checkout-attribution.js` file, verifying the old HTML responds unchanged. Never perform a generic app deployment.

## Commercial evidence boundary

The scheduled social posts are **scheduled** and were still `PENDING` when last examined. Preserving UTM can improve later campaign attribution but does **not** prove a human click, created invoice, completed 30 TRX payment, sold challenge, trader hire, or earned revenue. An actual paid sale and permissioned rewards remain separately verifiable.

Safeguard: the old source had no separate script and the only current product landing checkout link is preserved. This does not touch or grant live real-money brokerage trading to challenge customers.

## Existing source release publisher: pinned four-asset v2 with historical rollback support

The initial full CI attempt correctly blocked the source change because an older one-time static-only publisher in `scripts/mojprop_starter30_static_release.py` pinned the **previous Git blob** for `index.html` and exactly three files. That fail-closed safeguard was not disabled. The publisher now explicitly reviews these **four** immutable Git source blobs:

| Static asset | Git blob SHA-1 (identity, not a signature) |
|---|---|
| `index.html` | `0453939e3b40304d542a7e8e75f4bef6a9f99280` |
| `journal-template.csv` | `2d732321f1c1f431685e514789cf26bf2a977d84` |
| `journal-guide.txt` | `1e02213de4bed3fc9211e388b3f8b135ef2c0f0a` |
| `checkout-attribution.js` | `dbf6035a9cfeb65dd92995d1302081123ebfbe5c` |

New future manual static releases use `mojprop.starter30.static.v2` and include all four verified files. The old `mojprop.starter30.static.v1` manifest with exactly the historical three files is **still accepted exclusively for rollback** of previously recorded releases. A v2 manifest missing the new script is refused; a tampered/missing script file is refused before any write. All original no-symlink, no-hardlink, owner/permission, create-only atomic deployment, approval flag, private manifest and customer-asset protection logic remains.

Targeted tests at pinned PR commit `e7145305932ccbf2a8eba3d7fc67477cc3616115`: **32 static release tests, 12 reviewed-source tests, and 3 attribution tests, all passing**. Includes direct old-v1 rollback and new-v2 bad-manifest rejection checks; no live installation occurs during tests.

A second historical multi-page catalog publisher `scripts/update_mojplaywin_moj_prop_catalog.py` is a separate, non-authorized broad deployment and must **not** be used to overwrite any current live content. The scoped static page and its own reviewed four-asset publisher are the safe release lane for this fix. This PR merges source only and never triggers a deployment or payment transaction.
