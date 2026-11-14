# C22 — Four-week Moj Prop participant evidence: current parent reconciled

**One original Instagram and one original Facebook post per confirmed 28-day enrollment, not daily posting.** The challenge contract applies only to prospective v1.2 cohorts. This is a source-only, internal, human review feature, not a public trading/billing endpoint.

## Actual source fixes retained in latest parent PR #2310
The evolving parent independently fixed (a) both obsolete social test modules to the one-post 28-day contract, (b) the review-status label in the existing 0004 migration, and (c) a read-only Django admin view of the enrollment and the 28-day social proof. C22 **does not remove, overwrite or recreate** those parent improvements; no redundant 0005 migration is included in the final diff.

## C22 incremental security improvements
1. The original URL validator blocked the literal Instagram handle but not the linked Facebook Page ID 102203064721826 or Metricool brand ID 7317306. These are now blocked across both allowed Meta hosts, along with URL percent-encoding, non-ASCII confusables, backslashes, bad nested post paths, userinfo, ports, query strings and fragments.
2. The original evidence could be reassigned or altered by saving the Django model directly after participant submission or independent staff approval. The social-evidence model now freezes account, enrollment, platform, original URL and posted-at values from initial submission; a final human review cannot silently be rewritten. Direct model validation also requires actual staff identity and review timestamp not in the future.
3. Focused adversarial regression checks cover forbidden owner account IDs, URL tricks, immutable accepted/rejected evidence, unqualified reviewers, future-dated attestations and readonly admin registration. Parent's own 28-day contract/migration/phase-one and phase-two coverage is retained.

**Limits:** Django model \`save()\` validation does not protect against direct SQL or \`QuerySet.update\`; the production DB must have restricted credentials and immutable independent audit evidence before launch. A synthetic test enrollment is NOT an actual 30 TRX payment. Human attestations do not prove a post remained visible without independent observation. The entire social requirement remains subject to financial promotion laws, consent and contract review in each supported jurisdiction.

**Absolutely prohibited destination:** \`Dr.mojtaba.rozegar\`, linked Facebook Page ID 102203064721826 and Metricool 7317306. No posts/queues/campaigns anywhere on that personal account. No social publishing actions are added.

**No paid challenge, no TRX payment, no broker trade, no customer email, no deployment, no second bot.** The only company bot identity remains \`mojtaba.bot.ai\`.
