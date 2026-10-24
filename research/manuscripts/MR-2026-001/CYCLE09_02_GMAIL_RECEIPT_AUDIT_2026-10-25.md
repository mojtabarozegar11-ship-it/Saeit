# MR-2026-001 | Cycle 09 | Gmail evidence audit
Date: 2026-10-25; connected Gmail search was executed on both **primary** (mojtaba.rozegar11@gmail.com) and **company** (zomorodmelal@gmail.com) accounts.
Exact query, independently applied to both accounts:
```gmail
("manuscript" OR "submission" OR "Agricultural Water Management" OR "Discover Agriculture" OR "Frontiers in Plant Science") after:2026/09/01 -in:trash -in:spam
```
- Primary: results include GitHub review notifications, including PR #1045 (message IDs 1a16b5a8e7821f57 and 1a16b5938f643c1b), and unrelated automation/workflow emails. No publisher submission receipt was identified **among the returned results**.
- Company: 0 matching messages returned by this query. This is NOT proof that no submission exists in another account, folder, date range or unsearched journal portal.
- Scope limitation: only two named connected Gmail accounts, query range after 2026-09-01, up to 25 returned results per account. Third connected social account was not searched. Sender/body verification is not a substitute for an official manuscript portal receipt.
- Evidence: [GitHub PR #1045](https://github.com/mojtabarozegar11-ship-it/Saeit/pull/1045) and primary Gmail message URL https://mail.google.com/mail/u/?authuser=mojtaba.rozegar11%40gmail.com#all/1a16b5a8e7821f57.
Submission status: NOT SUBMITTED based on project ledger; no independently authenticated publisher Manuscript ID.
