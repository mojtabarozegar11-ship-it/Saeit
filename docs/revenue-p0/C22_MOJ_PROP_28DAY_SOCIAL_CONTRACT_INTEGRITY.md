# C22 — MOJ PROP existing v1.2 social review, reproducible four-week proof

**Source branch:** isolated Draft stacked on current MOJ PROP parent PR #2310. **Not deployed, not a customer-facing enrollment, no money charged.**

## Actual root causes fixed

1. Existing parent v1.2 policy explicitly requires **one original Instagram post and one Facebook post for the entire 28-day challenge**, each publicly visible for at least 28 days, starting from the independently reconciled paid enrollment. It does **not** require six daily posts or new posts every trading day.
2. Two existing test files still asserted the superseded daily-post design; one tried to import \`utc_day\` which the current social policy no longer exports, and the other used an old \`trading_day\` submission signature rather than \`PropChallengeEnrollment\`. This made the current full social test suite unusable as commercial release evidence.
3. The existing \`valid_platform_post_url\` rejected the visible Instagram handle \`Dr.mojtaba.rozegar\` but did not block the linked FB Page ID \`102203064721826\` and Metricool brand ID \`7317306\` in candidate paths. A disguised/percent-encoded path could also bypass literal string detection. Fail closed on those identifiers across both Meta hosts, encoded/control/unicode paths, invalid path shapes, spoofed domains, userinfo, ports, queries and fragments.
4. A reviewed \`PropSocialEvidence\` record was mutable through its model \`save()\` despite the human-review service refusing a second review. The model now refuses reassigning original account, paid enrollment, platform, URL or publication timestamp, and refuses changing a final review status, reviewer, date or attested visibility flags. It also requires a staff reviewer and a nonfuture review date. **Django \`QuerySet.update\` or direct database writes bypass model validation**; server DB access, audit triggers and append-only independent proof require a separate production control.

## Contract and implementation boundaries

- Four-week clock begins at **confirmed, independently settled purchase**, not a user-entered date. A post within the first 24h must mature for its own 28 days. Phase one and phase two share one pair of reviewed original posts per paid enrollment.
- A settlement event in unit-test fixture is **simulated DB state**, not proof that an actual 30 TRX transfer occurred.
- The challenge fee, broker-backed funded accounts, customer onboarding, payment, trading and social publication all remain disabled. A valid post does **not** open a paid account or generate capital.
- Business/legal risk still open: financial advertisement rules, explicit customer consent, material connection, disclosures, legality of post requirement, accessible alternatives where applicable, dispute/refund rights, real broker and collateral. The software alone does not make the promotional condition lawful.
- The public owner profile \`Dr.mojtaba.rozegar\`, its associated Facebook Page ID and Metricool brand ID are **100% prohibited destinations** for any scheduling, publication, advertisement or campaign. This patch does not connect to Meta or publish anything.
- Operational brand \`mojtaba.bot.ai\` is the sole bot; no new worker, scheduler, public POST endpoint, token, wallet or customer message is introduced.

## Release gate

Run the exact-host source CI and confirm all old plus new policy, social-review DB and unique constraint tests, Django check and no migration drift. Separately review source conflicts against PR #2321 and current parent, because PR #2321 may contain an older daily-post model. Never merge a stale model that replaces four-week terms with a daily-post requirement.

**No claims of actual cash, real customers, production activation or legal authorization.**
