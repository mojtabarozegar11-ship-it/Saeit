# MojTrade research product artifact

The trader now has a private, versioned packaging boundary for its read-only
market research output.

`scripts/mojtrade_build_research_product.py` accepts only the existing
research consumer report. It rejects expired reports, non-research execution
states, nonzero order counts and malformed signals. The resulting artifact
contains a SHA-256 of the exact source report plus explicit flags:

- `research_only=true`
- `execution=disabled`
- `orders=0`
- `publication_enabled=false`
- `delivery_enabled=false`
- `revenue_verified=false)
- `trading_pnl_included=false)

This is a private QA/delivery-ready artifact, not a public product listing.
It does not create an order, send email, charge a customer, settle a payment,
place a trade, or claim profitability. A future commercial release requires
separate owner approval, a lawful delivery channel, an actual customer order,
provider settlement evidence, and independent reconciliation through
`financial_core.revenue_evidence.verify_customer_revenue`.
