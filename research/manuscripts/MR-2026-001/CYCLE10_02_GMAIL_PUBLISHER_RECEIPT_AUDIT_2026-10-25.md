# MR-2026-001 | Cycle 10 | Independent publisher-receipt Gmail audit
UTC: 2026-10-25T00:02:35.098Z. Connected Gmail accounts actually searched: primary `mojtaba.rozegar11@gmail.com`, company `zomorodmelal@gmail.com`.
Queries run independently on **both** accounts (verbatim):
```gmail
("Agricultural Water Management" OR "Discover Agriculture" OR "Frontiers in Plant Science" OR "Manuscript ID") -from:(notifications@github.com) -in:trash -in:spam
(from:(editorialmanager.com) OR from:(springernature.com) OR from:(elsevier.com) OR from:(frontiersin.org)) after:2026/09/01 -in:trash -in:spam
```
Result: primary 0 matching messages for first query and 0 for second; company 0 and 0. A separate broader search of terms manuscript/submission/editorial after 2026/10/01 returned GitHub notifications in the primary account, not authenticated publisher receipts; company 0 in that broader search.
Limitations: Gmail syntax/search indexing, account scope, exclusions of spam/trash, sender aliases, third connected social account not searched, publisher portals not inspected. **Do not infer universal absence of submission from negative inbox searches.** Project submission ledger remains NOT SUBMITTED, with no journal, date, Manuscript ID or official receipt.
No messages sent, deleted or modified. Next valid proof: publisher portal record and/or signed publisher acknowledgment, not a GitHub notification.
