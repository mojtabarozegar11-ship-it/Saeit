# MOJ-PROP-01 XAUUSD v1.3 — draft risk review (not in force)

- **Product:** genuine prop challenge `MOJ-PROP-01`; NOT `MOJPROP-STARTER30` educational product.
- **Old contract:** `2026-11-15/v1.2` remains unmodified. `prop_firm.rules.POLICY` remains 0.8% trade / 1.6% aggregate, with real orders and checkout off.
- **New draft:** `2026-11-17/v1.3-XAUUSD-DRAFT` supports only Plan 1, USD $100 tier, XAUUSD, nominal 3% single risk and 8% aggregate open risk.
- **Binding loss rules unchanged:** 4% daily and 8% total equity drawdown. Projected stops must remain strictly above BOTH floors even with the nominal 8% open-risk allowance.
- **Risk basis:** `(distance(mid, stop) + full spread + adverse slippage reserve) * lot quantity * ounces per lot + round-trip all-in USD fees`, plus all pre-existing remaining-to-stop losses. Requotes/gaps may exceed this estimate.
- **Boundary:** no owner fiat funding, TRX settlement, live order placement, site release, customer enrollment or legally binding v1.3 agreement is implemented here.
- **Data warning:** input booleans are caller claims, not independently authenticated broker/KYC/funding evidence; require signed broker reconciliation and external legal/treasury approvals before any release.
- **Required integration:** explicit version selection in validated signed customer contract; broker-account-specific symbol/specs/quotes and full open positions; review and regression tests of core policy, accounting, KYC and historical cohorts. Main-only LiteFinance $0.80 risk envelope is still old and is NOT superseded by this file.

Read-only test: `python -m unittest tests.test_xauusd_v13_preflight -v`.

Source baseline: draft PR #2310, head `0a1e84ecbb691dbc1ba8dbca0ec0bcf0486884d8` (2026-11-17). No authority to trade or collect 30 TRX is conferred by passing these tests.
