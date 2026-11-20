# MOJ-PROP-01 XAUUSD v1.3 — broker/source evidence and demo qualification boundary

**Status:** NONPAYABLE DRAFT, no account opening, brokerage orders, collection of 30 TRX, external email, KYC processing, public sales, or deployment. Source review date 2026-11-17.

## Independently sourced public instrument facts (not account-specific confirmation)

LiteFinance publicly lists XAUUSD standard contract size **100 troy ounces/lot** and public minimum tradable volume **0.01 lot** (1 troy ounce at minimum volume). Its instrument summary reports a lot step of 0.01, but specifications and margin are explicitly subject to account/market variation. Relevant official pages:
- https://www.litefinance.org/trading/trading-instruments/commodities/
- https://my.litefinance.org/trading/info?symbol=XAUUSD
- https://www.litefinance.org/termsofuse/

**These pages are insufficient** to prove this particular customer/organizer account exists, its margin is currently sufficient, its FX/metal spread, any commission or swap, or that an unrelated challenge participant may instruct orders. Do not infer delegation authority from account credentials, an HMAC packet or public specifications.

## Account-specific evidence STILL REQUIRED from independent authenticated source

1. Correct LiteFinance legal entity and contractual jurisdiction applicable to the actual holder; whether the exact proposed prop-firm model is lawful and permissible under account terms.
2. Broker's explicit written permission for authorized third-party strategy/order routing **without sharing the account holder's password or 2FA**; withdrawal rights remain solely with the authorized holder.
3. Current authenticated USD account type, broker account holder identity (checked privately), symbol XAUUSD, position size minimum/step, 100 oz per lot, stop-distance restrictions, close-out rules, supported API.
4. Timestamped signed quote with exact bid/ask/spread; mark quote stale after 5 minutes. Margin and available free margin at the exact planned trade size, plus maintenance margin and stress buffer.
5. Current round-trip commission, carry/swap, fees, adverse slippage budget, gap behavior. Any unpriced cost means risk unknown and blocks trade.
6. All currently open positions and remaining loss-to-stop, reconciled by stable broker position IDs; strict 3% single risk, 8% nominal open risk and 4% daily/8% total equity floors.
7. Independent evidence of genuinely unencumbered USD 100 initial risk allocation **within the organizer-controlled account**; do not treat a demo balance or user assertion as capital.
8. Written controls for authorized order access, broker interruption, stop execution, real-time equity/drawdown, terminal outage, adverse slippage and account-owner action.
9. Separate legal/KYC/AML, beneficiary, region and refund rules; independent TRON payment confirmation; bound signed FA/EN agreement; backed-up and restored private ledger.
10. Contract condition of minimum **50 distinct reconciled closed positions TOTAL across the two simulated phases**, six independently verified trading days in each phase, and **no social posts required**. Historical source conflict must be resolved before sale.

## Code boundaries and unresolved defects
- `prop_firm/rules.py::assess_challenge` still requires an Instagram/Facebook post for historical v1.2 phase 2 and accepts only older contract versions. **Never pass v1.3 through it as a hidden migration.**
- `prop_firm/xauusd_v13_qualification_preview.py` reviews mathematically whether two phases and unique closed trades would pass under draft v1.3, but gives **zero authority** for a buyer agreement, capital, payment, login, trade or payout.
- `prop_firm/xauusd_v13_contract_gate.py` deliberately reports the historic 50-per-stage vs 50-total contradiction as an unresolved blocker.
- For this PR, the existing dedicated risk workflow executes new XAUUSD preflight and signed evidence tests, but does **not** execute `tests/test_xauusd_v13_contract_gate.py`, `tests/test_xauusd_v13_draft_terms.py`, or `tests/test_xauusd_v13_qualification_preview.py`. An attempt to change that workflow was blocked previously; do not infer green CI covers those unexecuted suites.
- A signed packet verifies integrity of the trusted adapter's statement, not independent broker identity, ownership, real market quotes, actual net capital or legal delegation.

**Release verdict:** NO-GO until fully independent documentation and specific owner deployment/spending approval. Passing mathematical or source checks does not constitute revenue, bank funding, broker confirmation or completed sale.
