# MOJ-PROP-01 — lawful commercial split and payment authority

**Owner-approved business concept:** An Iran-resident individual owns all trading capital; no trader deposits, receives, withdraws or owns that capital. Qualified traders may contract for performance-linked compensation under applicable employment and broker terms. **Do not call the owner a foreign incorporated firm or assume a banking/crypto license covers forex trading.**

### Distinct services
1. **Free trader recruitment:** application and equivalent recruitment assessment free of charge; no employment guarantee. A purchased test cannot be a concealed job application fee.
2. **Independent paid simulated skill evaluation:** genuine stand-alone performance assessment with scorecard and deliverable even when buyer is never hired; proposed price 30 native TRX for lawfully eligible non-domestic buyers only. This is NOT the educational product `MOJPROP-STARTER30`.
3. **Owner's proprietary trading:** trading capital stays in owner's account; separately approved broker execution; trader pay based on realized attributable profit under lawful service/employment agreement.

**No existing signed buyer agreements are amended.** Current v1.4.1 social-media mandatory-post terms remain a DRAFT; a later separately reviewed version should remove promotion from hiring/evaluation criteria or make an independently lawful opt-in program. Do not silently change existing contracts.

### Specific legal references
- Iranian employment agency regulation, Art. 7 note 2 (paid nationwide recruitment/placement calls): https://www.ekhtebar.ir/آیین-نامه-اجرایی-قانون-مجازات-اشتغا/
- Iranian Central Bank crypto policy, 1403/09/13 section 2: crypto assets cannot be used as domestic payment: https://hoghogh.ai/circulars/c-510162e6
- Iranian crypto-broker rules, 1404 article 38 (no using crypto assets as payment by crypto brokers) and article 3 (approved service scope): https://hoghogh.ai/circulars/c-2276965e
- Iranian Electronic Commerce Law arts. 33–39, consumer information/withdrawal: https://law-ir.ir/law/cat/1656/
- LiteFinance official customer contract and territorial restrictions: https://www.litefinance.org/company/documents/

### Payment wiring prerequisites
- Domestic Iran buyer -> local-lawful IRR merchant + PSP, with explicit IRR price. Never present a payable native TRX invoice.
- Foreign buyer -> native TRX only if a competent independent review confirms the actual Iran-resident owner's international merchant rights, the buyer jurisdiction, sanctions/provider rules, AML/KYC, consumer refunds, and receiving-wallet custody; foreign IP alone proves nothing.
- Existing `services/mojprop_real_plan1_tron_candidate.py` strictly matches a future 30,000,000 SUN solidified TRX candidate but **does not settle**, book revenue, issue invoice, receipt, or enrollment. Use authenticated independent SolidityNode data per https://developers.tron.network/docs/confirmation-semantics .
- Durable merchant order must persist actual buyer, independently signed/accepted specific FA/EN terms, payer wallet, exact SKU, authorized recipient, expiration and legal decisions. Commit against a global unique `(network, txid)` settlement ledger in one transaction and activate `PropChallengeEnrollment` only after that commit. Staff and customers cannot self-attest authorizations.
- `services/mojprop_commercial_lanes.py` is a **preinvoice router**, intentionally has no payment side effects and must not be called directly from client flags.

### Evidence absent today
Verified issuer/scope of claimed central bank type-2 license; binding classification of evaluation versus paid recruitment; authorized domestic IRR merchant account; independently cleared Iran-resident seller foreign TRX receipts; real customer acceptance; broker permission for owner-only automated execution of hired trader signals; fully restorable off-host production backup; production-integrated merchant/receipt/fulfillment and approved launch.

**No authorization to deploy, accept money, advertise guaranteed hiring, enter real trades or incur cost is implied.** This is a versioned, concrete technical/contract boundary, not proof of legal approval or a live gateway.
