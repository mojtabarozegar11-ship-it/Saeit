# MojPlayWin — canonical wallet and legal-record reconciliation (2026-10-24)

> Scope: merchant wallet proof, owner-reported legal dossier status, and per-SKU commercial-rights metadata. This is an evidence-backed operational correction, **not** automatic legal approval or a release.

## Source of truth

**Merchant signatures: VERIFIED — never re-request ownership signatures based on stale audits.**

Live host read-only audit on 2026-10-15 returned:
```text
ASTRA_LIVE_PAY_MERCHANT_WALLET_ETH_PROVEN=True
ASTRA_LIVE_PAY_MERCHANT_WALLET_TRX_PROVEN=True
```

- Completed GitHub Actions: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38790370883
- Review record: https://github.com/mojtabarozegar11-ship-it/Saeit/pull/187

These findings supersede older 2026-10-15 reports created *before* the signatures were submitted. If the live proof later changes, report the **new contradictory evidence and timestamp**, rather than treating old reports as current. A payer's future transaction signature is separate from the merchant's already verified wallet-ownership proof.

**Legal dossier: owner reports completed.** The owner's 2026-10-24 instruction is to stop re-opening the legal dossier or requesting documents/signatures already completed. This statement is an owner representation, **not per-asset commercial-rights evidence**.

**SKU-specific rights record: NOT RECONCILED for products 72, 225 and 879.** A live read-only audit on 2026-10-24 showed `metadata.rights_cleared=false` for all three SKUs; https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40062660655 and https://github.com/mojtabarozegar11-ship-it/Saeit/pull/1094 . The correct interpretation is that the *commercial clearance field* is missing/false for the currently observed product/version record. This is **not proof the overall legal dossier is incomplete or that the owner lacks rights**. Neither does the owner's general statement authorize silently setting a specific SKU true.

## Mandatory audit state model

| Dimension | Correct value from available evidence | Prohibited inference |
| --- | --- | --- |
| Merchant ETH/TRX ownership proof | verified 2026-10-15 | "Please sign again" |
| Legal dossier | owner-reported completed | "Legal case is uncompleted" based on rights flag |
| SKU 72/225/879 commercial clearance metadata | false / per-SKU evidence reconciliation pending | "Owner has no copyright" or "Set true automatically" |
| Historic orders | 9 pending/awaiting_chain in 2026-10-24 snapshot | "Paid" without settled chain proof |
| Paid delivery | no independently proven mainnet end-to-end commercial acceptance | "Payment flow is live and successful" from green unit tests |

## Reconciliation procedure — once per exact product/version

1. Locate the **already existing** owner legal dossier and its approval record without requesting another signature.
2. Match each distinct product ID, author/asset attribution, license/third-party inventory, current version and SHA-256 of sale asset to the appropriate signed/reviewed evidence.
3. Record provenance links, review date, approver identity and approved scope in a private audited release record. Detect missing or mismatched sources and report *precisely that mapping failure*.
4. Only after successful evidence reconciliation, update `metadata.rights_cleared` for the matching SKU via the system's authorized auditable admin/release workflow (not via a direct anonymous or inferred field flip). Never backdate or manufacture legal approval.
5. Keep the public TRX new-invoice fail-closed check strict (`rights_cleared is True`); preserve settlement, older invoices, legitimate buyer entitlement and prior downloads.
6. Independently reconcile all pending payment intents with real mainnet settlement before claiming any paid delivery.

## Non-regression policy for hourly agents

- Cite the **run ID** and differentiate `owner-reported`, `record-missing`, `verified` and `blocked`.
- Never use old "unsigned merchant wallet" messages in new reports unless a newer live verification explicitly invalidated both current proofs.
- Never equate absent commerce metadata with a legal determination, or flip rights approval flags without per-SKU evidence.
- Do not delete historical audit records or payment evidence. Supersede inaccurate **current interpretations** with this record.
- Canonical discussion and corrective checklist: https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1096

**Release boundary:** This record does not enable sales, settle orders, run a payment, deploy code, or change customer data.
