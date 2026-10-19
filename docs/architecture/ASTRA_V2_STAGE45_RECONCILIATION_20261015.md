# Astra 2.0 — Stage 4 to 5 migration reconciliation, 2026-10-15

## Grounded engineering result

The original VPS factory has applied migration 0048_business_market_architecture. The Astra V2 working branch has Django core migrations only up to 0039. The Saeit branch factory/staging-reconciliation-20261008 contains the nine missing historical migrations 0040 to 0048. The common 0039 migration has identical SHA-256 in both branches. This resolves the identity of the missing historical source but does not resolve model/code integration or establish sale-readiness.

## Verified audit trail

1. [Real read-only VPS schema audit 38679612254](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38679612254) succeeded: 11 independent guard tests; original factory latest migration 0048, 209 Product records, 479 ResearchSource rows linked to Evidence, 3 accepted private Astra V2 specialist families, 0049 schema missing. Original research schema is compatible with limited read-only inventory. These source links are not proven market demand.
2. [Cross-branch parity gate 38679896802](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38679896802) succeeded: 9 guard tests, common 0039 migration SHA identical, nine historical files 0040-0048 missing on Astra branch, zero differences at shared migration numbers, no automatic merge performed.
3. [Disposable 0048 database proof 38680015950](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38680015950) succeeded: historical 0048 source independently checked out, dependencies installed, Django migrations fully run in a clean ephemeral CI SQLite database. Confirmed nine migration records 0040-0048 and BusinessUnit, MarketPolicy, LegalEntity tables. No VPS SSH connection or production credentials.
4. CI and Django CI passed after code and workflow additions. The new schema and migration diagnostic scripts perform no writes to live databases or websites.

## Integration plan and non-negotiable safety constraints

- Establish a separate, isolated integration baseline from the trusted 0048 historical source inside Saeit. Reconcile core model definitions, task/runtime policy, Django migrations, protected routes and payment-related code deliberately; source branches have hundreds of diverged commits. Do not merge the historical source wholesale into the live site or directly copy nine migrations without their corresponding models.
- Verify code/model/migration consistency with migration check and exact isolated test suites. Only then develop any successor to migration 0048 on a reconciled branch. Never create 0049 directly from current 0039 branch or run it on original VPS.
- Test a new Stage 4 to 5 evidence-queue model with a disposable database before any actual VPS copy. A successful clean SQLite migration is not proof of safe real-data conversion, rollback or compatibility with a live 0048 dataset.
- Preserve raw source citations, research credibility, date/time, provenance, source content hashes, rights checks and actual buyer-value evidence. A citation counter alone cannot become a certified product-market opportunity.
- Maintain a separate private technical production lane while 0049 is absent. Keep automatically generated synthetic lessons and same-source ZIP rebuilds distinct from actual market-validated saleable products.
- Before commercial release, prove external user value against university alternatives, independent economics/agronomy validation, usability, licensing, support requirements, a justified price, customer checkout and reconciled settlements. Do not fabricate quality scores, 90% discount base prices or income.
- Require staging backup/restore proof, bounded queues, write lock, migration rollback plan, no live-site or payment effects, and observed running health before any controlled cutover.

## Acceptance matrix

| Criterion | Status |
| --- | --- |
| Original VPS 0048 migration observed read-only | PASS |
| Trusted same-repo 0040-0048 files located | PASS |
| Common 0039 SHA verified | PASS |
| Nine migrations tested in disposable CI SQLite | PASS |
| Correct 0048-model integration branch built | NOT DONE |
| Proposed 0049 successor migrated against safe data copy | NOT DONE |
| Provider-backed market Stage 4 to 5 accepted | NOT DONE |
| 24-hour integrated soak | NOT DONE |
| Retail/commercial product quality independently assessed | NOT DONE |
| Products published, settled revenue verified | NOT DONE |

**Conclusion:** The historical migration-source gap is identified and a complete safe reproduction of migrations through 0048 has been demonstrated on an empty temporary database. Full original factory Stage 4 to 5 cutover is not yet safe or complete. Keep PR 101 as draft, websites and wallet/payment services unchanged.
