# Finance102 — verified release gate (13 November 2026)

## Live / source distinction

- **Existing public pages:** 102/102 accessible (34 Persian on Zomorod Melal; 34 English and 34 Arabic on MojPlayWin). Their CTAs lead to two functioning HTML shop **landing pages**, not proven transactions. Read-only audit [43403675324](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43403675324).
- **Proposed education expansion:** 102/102 guide variants prepared and tested in source; 51 brand/language case studies and 102 allowlisted canonical URLs; new revision marker `finance102-20261113-v2`.
- **Live rollout of proposed changes:** 0/102 verified on that public audit. Original HTML template source remains unchanged, blob `9189b3fc292cad19cd661ad082039a93b8c98d2e`.
- **Commercial:** 51/51 signal pages explicitly say no real live signals; 51/51 substore pages say no active dedicated checkout. No positive proof of purchase, user delivery, settled income, or legal sale readiness.

## Most recent protected-path evidence

- GitHub hosted runner could establish TCP to 30GB hosting cPanel `178.239.147.125:2083` and `:443`; VPS SSH `178.239.147.150:22` and cPanel SSH `178.239.147.125:1396` were unreachable. See [43404069433](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43404069433).
- The account's historic UAPI hostname `zohal.pws-dns.net` did **not** satisfy the exact expected IPv4 DNS mapping during credential-free preflight [43409609456](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43409609456). TLS certificate identity therefore remains **unverified**; the script refused to initiate a TLS handshake against a mismatched destination. This is not evidence that the HTTPS port is closed or the hostname is malicious.
- The UAPI client now supports both `/execute/` root JSON and an explicitly identified API-v3 wrapper. It **refuses to transmit any token** if both exact expected DNS mapping and CA-verified TLS/SNI are not proven. The client is a manual-only GET to `PassengerApps/list_applications` and cannot upload, change, or delete files.
- The cPanel API endpoint is documented by [cPanel UAPI Introduction](https://api.docs.cpanel.net/cpanel/introduction) and [cPanel API Tokens](https://api.docs.cpanel.net/cpanel/tokens). Creating a token is an account-owner action. It may permit write APIs; do not treat it as harmless. Never place a token in the repository, PR, issue, chat, debug trace or artifact.

## Exact source scope of any eventual content publication

Two application code paths **only**, separately in each verified owning Django root:
1. `core/finance102_guides.py` — proposed educational text, no database or payment actions.
2. `core/financial_brand_pages.py` — scoped render integration, canonical, content language and release witness headers.

The existing `core/templates/core/financial_brand_page.html` is **not** a publication target. No changes to the home page, current CSS, shared templates, customer or merchant stores, account system, orders, payments, `.htaccess`, database migrations, or independent child sites are permitted under this scope.

## Release prerequisites — all must be proven, not assumed

1. The account owner establishes the genuine cPanel HTTPS hostname for the live 30GB account with independently verified DNS, certificate and account ownership. Do not weaken CA or SNI checks or copy credentials to unverified hosts.
2. Re-establish authenticated read-only access; verify the true live root for each domain using `PassengerApps/list_applications`, retaining only sanitized identity/mapping flags.
3. Read **exact current on-host file hashes** of the two code targets per app. A production record in GitHub is not enough to establish their current bytes. Check for independently modified host-only code and protected child apps.
4. Verify disk headroom and restorable private backup of any existing target, ensure no non-target file/worker/template mutation, rehearse rollback. A shared Passenger app that would restart unrelated child sites is a release HOLD.
5. Explicit operator authorization for the exact proposed production action, followed by least-scope, SHA-pinned installation and independent verification; no generic merge-triggered legacy deploy.
6. Re-run the strict release audit `python -B scripts/finance_102_public_audit_20261113.py --require-release` on its audit branch: it requires **102/102** correct revision, canonical and Content-Language headers plus surviving public CTAs.
7. Independently prove paid product availability, settlement, receipts, fulfillment and legal disclosures before any revenue claims. Do not fabricate signals or substitute public HTTP 200 for confirmed commercial functionality.

**At this cycle's close:** step 1 FAIL-CLOSED, steps 2–6 not executed, actual revenue still unverified. GitHub unit CI is source evidence only. No server writes, spending, payments, messages, token creation or worker restart were performed.
