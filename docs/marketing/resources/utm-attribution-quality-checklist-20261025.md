# Ethical campaign attribution checklist
Free measurement resource · MojPlayWin · 25 October 2026

A tracked link is **not** proof of a click, lead, or sale. This checklist separates campaign configuration from observed outcomes.

## Link specification
Use stable HTTPS destinations and consistently named UTM parameters:
- utm_source: actual channel (for example github, newsletter, youtube).
- utm_medium: actual distribution method (organic_referral, email, video).
- utm_campaign: a short, unique campaign identifier.
- utm_content: optional creative variant, never personal identifiers.

**Example only:** https://mojplaywin.com/?utm_source=github&utm_medium=organic_referral&utm_campaign=measurement_guide_20261025&utm_content=worksheet

## Preflight
Confirm the final URL resolves, the landing page has the expected content, redirects preserve attribution where lawful, and the page's privacy disclosure accurately describes analytics. Never place email addresses, wallet addresses, names, tokens or order identifiers in UTM values.

## Measurement record
For each published creative capture: platform, account, publication ID, timestamp and timezone, creative hash, destination, campaign parameters, intended audience and explicit call to action. Store only the minimum data needed.

## Funnel and denominator definitions
- Impressions: actual platform-reported displays, if available.
- Clicks: platform-reported link clicks; do not substitute page views.
- Sessions: analytics-reported visits under the configured attribution model.
- Leads: unique, consented enquiries matching a stated qualification rule.
- Purchases: independently confirmed completed paid orders, net of duplicates and reversals.
- Conversion rate: confirmed conversions / defined eligible denominator, with window and source disclosed.

## Quality checks
Compare analytics timestamps and timezones, exclude known internal testing, and flag attribution gaps rather than inventing values. Report **unknown** where no data is connected. Do not infer causality from a before/after change without controls.

## Weekly decision
Continue a channel only when the cost, data quality, audience fit and verified outcomes support it. A high click count without trustworthy sales evidence is not a validated revenue result.

[Official storefront](https://mojplaywin.com/store/?utm_source=github&utm_medium=resource&utm_campaign=measurement_guide_20261025). Product price and availability are deliberately omitted because they require live verification.