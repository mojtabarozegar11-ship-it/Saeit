# Autonomous editorial and publishing policy — three brands

## Intent
The content agent owns the routine lifecycle for personal, company, and MojPlayWin brands:
topic discovery -> source gathering -> evidence checks -> unique draft -> localization -> editorial QA -> channel-specific formatting -> scheduling -> publishing -> URL/receipt verification -> analytics -> improvement.

## Preconditions
Publishing is disabled until the owner connects and verifies each account, the platform's official integration is implemented and tested, and the owner grants initial publishing permission for that account. After that, routine low-risk content can be automatically published within the approved scope, without per-post owner review.

Never claim an external post was published without a verified provider post ID and URL or another trustworthy delivery receipt. Never publish through a draft generator or pretend that a workflow artifact is a published post.

## Safeguards
- Brand-specific accounts, credentials, content libraries, calendars, policies, audit logs, and metrics.
- No fabricated claims, citations, testimonials, prices, product availability, or financial outcomes.
- Respect copyright, privacy, consent, platform policies, rate limits, and opt-outs.
- Block duplicate, thin, and mass-spam content. Avoid cross-site link schemes.
- Fail closed on missing evidence, QA failures, expired credentials, unsupported APIs, and publication errors.
- Paid ads, spending, payment actions, sensitive commercial commitments, and first-time account authorization require owner approval.
- Use official APIs where supported, with secret storage, least privilege, retries, deduplication keys, and rollback/unpublish plans.

## Implementation status
This document records policy only. Current generator creates offline drafts. It has no platform publishing integration, credentials, or verified successful publications. Expansion to 30 sites and 30 blogs is deferred.
