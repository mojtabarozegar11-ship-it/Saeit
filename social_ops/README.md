# Two-brand Social Operations (isolated draft system)

This project is independent of the Django website and the digital factory. It does not create Google/social accounts, publish posts, spend money, or access production.

## Brands
- personal: Mojtaba Rozegar — use only the owner's approved portrait.
- company: Zomorod Melal Agro-Industry — use only the approved company logo.
- Keep identity, content calendars, analytics, contacts, and revenue reports separate.

## Operation
The scheduled GitHub Actions workflow runs a standard-library-only Python generator and uploads two independent JSON draft queues as workflow artifacts. No tokens or external API calls are needed. Posts are DRAFTS, not factual research or published content.

## Next integrations
1. Owner creates/verifies accounts with the providers.
2. Store platform tokens in GitHub Actions Secrets (never in source code).
3. Implement each platform's official supported publishing API with dry-run default, idempotency, rate limits, and audit logs.
4. Require explicit owner approval for initial external publication, paid ads, financial transactions, and sensitive commitments.
5. Add evidence-backed topics, editorial QA, deduplication, and analytics before scaling.

## Security
Never put Gmail passwords, OTPs, private keys, or personal birth information into the repository.
