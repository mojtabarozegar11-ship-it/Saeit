# First paid MojPlayWin product — technical and editorial prepublication review

**As of 2026-10-15 — DRAFT ONLY / NOT FOR SALE**

Product record **#72**, *The Science and Practice of Chess Improvement*, has a private on-host PDF and a provisional database price of **USD $7.50**. It is currently **inactive** and none of its merchant sale, editorial, copyright, or digital fulfillment permissions have been switched on.

## Independently verified

- Receiving addresses for both ETH and TRX have administrator-signed, cryptographically validated proofs in live MySQL.
- The PDF exists outside the public document root and is a private regular file, about **432,386 bytes**; header/trailer valid, no world-read bit.
- Actual PDF reader (strict parse) found **225 pages** and **36,778 English word tokens** — the user's minimum 200 pages / 35,000 words are met.
- PDF text on all 225 pages can be extracted; 87 pages contain at least 150 English words; median page 91 words, mean 163.5.
- No fully identical extracted-text pages and no repeated exact long paragraphs were identified by the checks; this is not a plagiarism or originality certification.
- Automated lexical indicators: chapter markers 96; exercise terms 89; solution terms 56; bibliography/reference terms 3; FEN patterns 4; move-notation matches 21. These approximate counts should NOT be treated as proof of advanced grandmaster-level editorial content, technical accuracy, or adequate illustrations/diagrams.
- PDF author metadata **does not match the previously declared author spelling according to an automated string check**. This does not establish the true author; reconcile metadata against an authoritative author declaration before releasing.
- Product #72 in the live Django database has **no owner FK** and **no linked published research article**. It has no verified license or quality fields, and no enabled private fulfillment policy.

## Technically repaired without starting sales

A narrowly scoped configuration change now sets `MPW_COMMERCE_PRIVATE_ASSET_ROOT` to the pre-existing private assets folder. A fresh Django process used the production `mpw_commerce.downloads._private_file` security guard to resolve **only** the privately held book, successfully. The original settings bytes have a private checksum-verified rollback copy. Homepage, store and admin login all returned HTTP 200 after the change, and all payment/customer collection feature flags remain explicitly FALSE.

Evidence:
- Initial live product and PDF structure: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38689582959
- Isolated complete PDF parse and word/page count, without uploading content: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38689828950
- Editorial and safe-root availability metrics: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38690036077
- Private asset root guarded release + healthy website: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38690361582

## Release blockers, fail closed

1. **Real editorial review** of full PDF for meaningful unique chess analysis, worked-out exercises, references, correct FEN/moves, diagrams, readability and scientific accuracy. Page/word counters are insufficient.
2. **Copyright, authorship and rights** evidence; fix PDF metadata if the owner independently confirms author identity. No fake approval, citation or originality claim.
3. **Commerce metadata**: link correct owner record and relevant *real* published scholarly article (if legitimately related), create a versioned private asset mapping, verify file digest and reasonable USD price, and record all quality/license/asset/publication check decisions. This must not silently enable live products.
4. **Buyer journey**: complete UI and an explicitly authorized very small real ETH/TRX incoming settlement with independent chain finality, secure invoicing, idempotent delivery and buyer access control, including refunds/support paths.
5. **No blanket catalogue or automatic publication**: only one independently approved book should go live after the gate review. Do not claim an original crossed-out price or large discount without real historical price evidence.

**Decision:** Technical PDF format/size and private file delivery root **PASS**. Editorial/rights and live financial acceptance **NOT VERIFIED**. Product #72 remains **inactive** and public checkout remains **OFF**.
