# MOJ PROP — Facebook share-card image: four exact English pages

Date: **2026-11-21**. This document inventories **already applied, scoped production changes**, not a release authorization to broadly overwrite the live application.

## Why

The first MOJ PROP free organic Facebook risk-education post was **actually published** at 10:15 Asia/Tehran, confirmed by connected Metricool (Facebook post ID `102203064721826_1454567966831650`, reported public URL https://facebook.com/1426780432943737/posts/1454567966831650). Its guide and the related English educational and qualified-trader landing pages had valid Open Graph titles and descriptions but **no OG share image**. The already-live Starter30 product page had a verified first-party 1600×900 WebP cover.

The owner already owns and serves that cover here:
`https://mojplaywin.com/design-preview-20261017/static/site/heroes/education-detail.ae7381d4181d.webp`
The asset returned HTTPS **200** `image/webp`, size **57,744 bytes**, actual dimensions **1600×900**; SHA256 `2c88014cc89450c0e0080675010d934582283a7eb029900854fad4fbddf5cc09`.

## Actual production action

Atomic, SHA-guarded changes to **only four current English MOJ PROP HTML documents**: risk management; drawdown and position sizing; simulation vs live; and selected professional traders. Added one same-domain `og:image` with its width, height, descriptive alt, and `twitter:image`; set the existing `twitter:card` to `summary_large_image` on guides and added one for selected traders.

No HTML structure, JavaScript, checkout, payment, business terms, copy, rendering styles, form, product pricing, user records, databases, app WSGI, root sitemap, factory or other domains were altered. This improves the *availability* of a share-card preview image; it does not establish that Facebook has refreshed a previously cached post, produced any clicks, or generated a sale.

The live `signals/index.html` file has known source drift (host SHA `34b05a98ec6fa1eee9d8c340c7cc72a400e109aa712cc113da446f28661720b0` vs GitHub SHA `866bc75490832b85255d1cba428dda8514ffd1a29b1c78d89c39c4b810371f16`) and **was deliberately excluded** rather than overwritten.

## SHA-backed backup and postflight

Private host backup and manifest:
`/home/zomorod2/separated-backups/20261121/mojprop-facebook-og-live-assets/`
Original HTML backups and manifest mode `0600`; directory mode `0700`. Roll back only after checking the current SHA equals the published SHA and atomically restoring the exact original, with no broad deploy.

| HTML page | Original SHA256 | Published SHA256 |
|---|---|---|
| education/risk-management/index.html | `be6f53906c5c745a56f3f72aad244baed0c046391214a820570c846feed4bae3` | `d7223161ed59fec43ae0e03584a85899ca32cc60c360f26d449fcd929433d84f` |
| education/drawdown-and-position-sizing/index.html | `6c914f0fc36ea9f446300bbbf4b527503b0d7a178635fe9ef4107a01105fb3b7` | `e8caff36b81234d7cb7b8461232ef2ae519ad8c5bf6416cc40bb5e3aa3fba11c` |
| education/simulated-versus-live/index.html | `76a38c51c0b72b198fec1d6f38e8795e2f623476f6a0f2c51acf710967e7c95b` | `ebc0e9bc15c8500de123f815226319d83e636e087338fbb9b1fa22a3cf22b1bb` |
| selected-traders/index.html | `626b5434c6a7fafb09cade617934c297a82afb5c339ee268a838f4f89ddf87d0` | `d99f1877ffd04aa98a003253afe4ce1da32155646869147fb6041eba13e57210` |

Each page independently fetched from public HTTPS returned **200 and byte-for-byte equality with the updated host file**. All four updated GitHub HTML source files were fetched via pinned commit `c527beab989ffe935db35efb4e7bcf52eb871267` and verified **byte-identical to live**. A new offline-only Python regression contract checks duplicate OG tags, same-origin image, original canonical links, original guide UTM script and Starter30 CTA, selected-trader distinction and absence of Facebook trackers; **4/4 focused tests passed** at source commit `eb33874525033da06bf0d5f4779f0a420784b023`.

Source PR must not be merged until both complete CI suites and other required checks succeed; source merge has no live effect as the four target pages have already been updated safely.
