# MPW buyer-email restore — reviewed source from earlier Draft, no release

## Why this work is distinct from a new unfinished payment feature
The main-based PR #2297 established a real versioned-source coverage gap: 6/11 expected buyer-checkout files, only 1/4 literal route declarations, and no integrated `mpw_commerce` package. The older Draft PR #2263 already contained the carefully reviewed buyer-email recovery service, immutable order-email claim models and a schema migration. This change **restores those exact reviewed source bytes** from commit `2c08f0155da5f3efa166906104c152dba6a40e1f` into a child Draft PR, keeping the source provenance and existing commercial guards. It is not a new checkout/payment implementation.

## Restore scope
- `services/mpw_trx_email_recovery.py` — retains exactly-one-POST-email check, immutable per-order claim binding, HMAC-salted token digests, token expiry and rate limits; mail requires BOTH `MPW_GUEST_RECOVERY_ENABLED is True` and `MPW_GUEST_RECOVERY_EMAIL_APPROVED is True`. The checked-in `config/settings.py` does not enable either; **no SMTP is sent**.
- `core/guest_recovery_models.py` — restores `GuestOrderEmail` (PROTECT one-to-one), `GuestRecoveryToken`, `GuestRecoveryRate`, with no implicit user permissions or raw recovery token in DB.
- `core/migrations/0049_mpw_guest_email_recovery.py` — reviewed CreateModel definitions, dependent on the already present `core/0040_commercefunnelevent` migration. This is a source restoration **not executing migrations**.
- `core/models.py` imports the three reviewed model classes; it does not modify any payment ledger, wallet or seller authority.
- The pre-existing safe read-only source-graph workflow now recognizes 8/11 required versioned buyer files. It continues to explicitly reject release because the `mpw_commerce` package's buyer orders, checkout view, checkout template, three buyer routes and INSTALLED_APPS registration remain absent from this reviewed root.

## Verification and explicit NO-GO
44 new independent source and migration tests and 105 existing checkout/CSP and source graph tests run offline with **no Django DB, SSH, cPanel, mail, paid checkout or blockchain network**. Full repository CI must separately confirm model and migration compatibility. No component should be wired into active routes until authoritative original `mpw_commerce` implementation and real effective cPanel root, applied migrations and rollback have been independently verified. **Do not fabricate paid claims or disable CSRF, verified buyer email, TRX finality, anti-replay or fulfillment gates.**

One organizational agent only: `mojtaba.bot.ai`. No spending, merging, deployment or customer messaging without separate owner approval.