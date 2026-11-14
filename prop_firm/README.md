# Proprietary trading policy engine v1.1

**Status:** Code for the proposed prop business. NOT a launched website, licensed provider, funded-account contract, broker adapter or payments service. The only organizational robot identity is **mojtaba.bot.ai**; this is an internal capability, not a second robot.

## Confirmed product terms
- **30 TRX per applicant** is the challenge participation fee, not the company's starting capital.
- Two *simulated* evaluation phases: realized-net profit goals **9.6% / 6%**, at least **6 valid trading days** each, maximum daily **4%** and fixed total **8%** mark-to-market equity loss; largest profitable day at most **32%** of net profit.
- **No completion deadline**. Inactivity notice after 78 days and 39-day grace; inactivity messaging is not implemented here.
- Upon passing both stages, KYC, lawful company funding and broker approvals, the first *real* account is **$100**, contingent on available capital.
- All **14 USD levels:** 100, 200, 400, 800, 1500, 3000, 5000, 10000, 20000, 35000, **50000**, 70000, 85000, 100000.
- **30-day promotion window**, at most one level per qualifying window, profit goal **3.6%**, at least **12 valid trading days**, no risk breach, max day 32%, trustworthy reconciled evidence and verified funding for the next tier.
- Per-trade stop-risk max **0.8%** and cumulative open stop-risk **1.6%** of tier capital; block an order if broker minimum lot/stop distance cannot fit.
- Monthly net profit sharing **70% trader / 30% company**, on cumulative realized net P&L exceeding previously *allocated* profit. Losses must be recouped first; no double payment.

## Non-negotiable implementation requirements
1. No actual payments or trade orders can be triggered by this module: both real execution and TRX checkout are disabled by policy.
2. All financial metrics must originate from verified, authoritative, timestamped brokerage or simulated-venue records; browser parameters are not trusted.
3. Daily equity floor: UTC day-opening equity minus 4% of original tier capital. Total equity floor: original tier capital minus 8%. Floating P&L counts. Trigger at or below either floor. Handle trading-day boundaries deterministically.
4. The 32% best-day rule is applied against **net realized profit**, not merely the sum of positive days; days with losses can increase the ratio. Phase two requires independent evidence of phase one pass.
5. Challenge acceptance, trade execution, settlement and promotion need durable idempotent records, transactional concurrency control, immutable audit logs, unique account/phase/period/transaction keys and dispute procedures. The pure functions do not provide these.
6. Funded real accounts require lawful eligibility, KYC/AML/sanctions screening, signed customer agreement, broker authorization, verified **unencumbered cash >= requested tier capital + payout reserve**, and independent operational signoff.
7. An authentic $100 account might not satisfy broker minimum order size on a given symbol. Do not relax order-risk bounds or invent fractional fills to solve this.
8. Bank/wallet settlement requires confirmation and safe ledger posting; payout calculations cannot transfer money. TRX receipt accounting must validate TRON mainnet transaction ID, recipients, exact onchain quantity, confirmation/finality, refund rules and taxes.
9. All customer-facing rules must be published before fee acceptance. No unilateral retroactive punitive changes; disclose capital scarcity and conditional escalation. Legal characterization depends on where the business actually operates and serves customers.
10. No independent trader bot or public branding is added. All bots/strategies are future subcapabilities of **mojtaba.bot.ai**, with old identifiers migrated only after validated handoff.

## Local automated checks (standard library only)
```bash
PYTHONPATH=. python -m unittest discover -s tests -p 'test_prop_firm_policy.py' -v
```

## Required gates before launch
Verified operating country and regulatory counsel; funded cash reserve and treasury policy; approved broker and its minimum order/stop specs; encrypted account store; KYC and eligibility; immutable and reconciled ledger; wallet and escrow accounting; customer terms and dispute handling; penetration/integration tests; hosting and domain authorization; independent deployment approval.

**No deployments, paid services, live trading, customer emails, asset deletion, or payments are permitted by this draft.**
