# MojPlayWin / English MOJ PROP — server-side traffic evidence

**Date:** 2026-11-21 UTC. **Status:** implemented and checked with authorized cPanel read-only logs, separate from consented client telemetry. No payments or orders created.

## How to run

Run: python3 scripts/mpw_measure_server_requests.py --days 7

Aggregates from two exact known first-party access-log paths only:

- /home/zomorod2/access-logs/mojplaywin.com.zomorodmelal.ir-ssl_log (current)
- /home/zomorod2/logs/mojplaywin.com.zomorodmelal.ir-ssl_log-Nov-2026.gz (archive)

The script extracts only scoped stage, method, HTTP status family, timestamp, and a coarse user-agent category. It deliberately **does not output or write IPs, user-agent strings, email addresses, order IDs, invoice IDs, wallet addresses, referers, cookies or original request URLs**. It does not connect to a database, network service or analytics provider.

A browser-looking user agent is **not proof of a human**. The origin logs may omit other hosted domains, have gaps, have forged user agents, or overlap archives. The 2026-11-21 check found the observed archive stopped at 2026-11-20 19:10:02 +0330 and the live log began 2026-11-20 19:20:06 +0330, so the sampled files did not overlap at that boundary. The approximately ten-minute gap must not be filled in.

## Live read-only checks

Seven-day window at 2026-11-21 03:18 UTC, rounded:

| Request stage | Browser-like GET HTTP 200 (not unique people) | Known automated GET HTTP 200 |
|---|---:|---:|
| /store/ | 31 | 82 |
| /commerce/book/{product}/ | 21 | 25 |
| /moj-prop/ | 59 | 543 |
| /mojprop-starter30-checkout/ | 7 | 45 |

In the sampled 7-day window, **no successful POST (HTTP 2xx/3xx) to store start-order or prop Starter30 checkout** was observed. This is consistent with a separate isolated SQL status check with no native TRX store gateway status rows created during that 7-day window and no Starter30 prop payment status rows there, but it is **not** proof of zero humans or causation for abandonment.

The active cPanel production app's read-only SQL status aggregation over 7 days showed old CommerceFunnelEvent facts view_store=62, view_item=53, begin_checkout=31. Do not mix these with the static /store/ route's Apache requests; these are not unique visitors or current customer conversions.

A 30-day store gateway status check returned expired=35 and paid=2. These are historical technical records, **not** proof of new revenue or two actual paying customers. Do not sum gateway status and payment proofs into sale counts. The isolated prop payment table had no status rows in the checked range.

## Limitations and diagnostic action

To measure verified unique humans, require actual voluntarily consented browser engagement and appropriate bot controls; raw web access logs cannot establish human identity. To identify a specific shopper abandoning after invoice issuance, instrument carefully scoped server-side events under the actual payment protocol and privacy policy; never infer a drop-off from absence of browser event on Django pages whose CSP intentionally blocks script execution.

No change to factory, WSGI, database schemas, payment code, cron or other domains was made by the server request counter. The private GitHub ledger reader is separate and accesses the existing active cPanel database **only through bounded read-only SQL transactions**.
