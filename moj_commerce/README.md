# MOJ Commerce — Secure Digital Fulfillment Foundation (DRAFT)

**As of 2026-10-21: SOURCE ONLY. NOT INSTALLED. NOT A MERCHANT PAYMENT GATEWAY.**

This is a Django 5.2-compatible slice for **multi-merchant order provenance, confirmed TRX proof reception, verified buyer entitlements, and secure bounded private ZIP downloads**. It builds on branch `feature/mpw-tron-pro-v01-20261021` and reuses `mpw_tron_pro.store_receiver_contract.verify_store_event`. It does not handle wallets, private keys, signatures for blockchain transactions, exchange, transfers, or seller payouts.

## Covered in this PR

- Explicit `Merchant` onboarding states `pending → approved → suspended`; no automatic auto-approval.
- Seller-owned, separately verified public TRON `MerchantAddress` addresses; one never shared with another seller and one used for only one invoice in this first pilot.
- Merchant-scoped ZIP digital product and price with immutable order snapshots and optional buyer accounts (pilot requires an authenticated buyer).
- HMAC-SHA256 machine-to-machine `POST /api/payments/tron/fulfill/` from the existing TRON Autopilot **plus an independently configured chain-verification callback** (mandatory; missing=503). Compare txid, destination, Sun, network, block, expiration, seller/product/buyer unchanged before granting any entitlement.
- Database constraints on payment txid, event id, order id, digital file, product SKU, receiver address, entitlement; PostgreSQL `select_for_update` and `transaction.atomic` for idempotent exactly-once entitlement creation.
- Signed short-lived 5-minute buyer-only download link, max 5 downloads by default, optional entitlement revocation; 100 MiB maximum; `sha256` each file before returning; private server-generated storage names, no path from HTTP parameters, `O_NOFOLLOW` protection for symlinks; no-store responses.
- End-to-end **synthetic only** test coverage for HMAC, wrong payment, cross-seller, duplicate, unauthorized buyer, tampered link, expiry, corrupt file, symlink, replay, and recovery.

## Explicitly excluded or blocked

1. No code is imported into `config/settings.py`, `config/urls.py` or production WSGI; `MOJ_COMMERCE_RECEIVER_ENABLED` is absent/off by default, and there is no actual verifier installed. Any accidental standalone receiver responds 503.
2. There is **no merchant signup approval process, verified-wallet ownership challenge, product ZIP intake/antivirus scanner, quote creation UI, payment address allocator, checkout integration, automatic monitor scheduling, multi-tenant admin dashboard, accounting, merchant commission charging, refunds, customer support or legal compliance signoff** in this slice.
3. The `MOJ_COMMERCE_FINALIZED_TRON_CHECKER(event, order)` **must** independently fetch the final block body and execution receipt from an approved TRON SolidityNode. It must not reuse event claims as proof, even though unit tests inject a synthetic checker. The checker is intentionally **not provided** so the live endpoint fails closed. Never set it to the test mock.
4. `MOJ_COMMERCE_PRIVATE_ROOT` must be a private non-public directory, not within Apache/Nginx/cPanel docroot, with owner-approved ZIP files stored at `<private-root>/<merchant-uuid-hex>/<file-key>.zip`. Files must be uploaded by an independently vetted ingest pipeline with malware scanning and SHA-256 verification. This project only serves trusted pre-ingested files.
5. Requires cPanel live `mpw_commerce` code inspection and approved mapping from its merchant/order identifiers into `Purchase`. This repo alone does not establish production state.
6. SQLite is used **only for isolated tests**. Real subscriptions/traffic require PostgreSQL and concurrency/load/rollback tests.
7. No public launch, payments, real TRX transfer, wallet secrets, production migrations or main-branch merge authorized.

## Contract and integration

Only an authorized trusted backend may create `Purchase` rows from an approved TRON quote, after validating SKU, product price, buyer authentication, merchant-approved address ownership and uniqueness. **Never use browser-supplied price, wallet, token, or on-chain proof.** The existing TRON engine should issue its invoice and atomically bind the buyer and merchant reference. The unique receiving address must be controlled by the seller. No merchant seed/private key is ever stored. Extend the proof checker to bind the expected destination and its seller association against the independently solidified TRON transaction.

Checkout & buyer interfaces remain separate from this receiver. When the TRON engine has independently verified payment, it issues the already-defined signed delivery event to `POST /api/payments/tron/fulfill/`. After both HMAC and independent chain proof pass, the Django receiver inserts an entitlement in a single transaction and replies with a stable `delivery_id`. A duplicate of the *same* event replies with exactly the same id. A different event/tx or order mismatch fails closed.

The authenticated buyer requests `GET /moj-commerce/orders/<order_ref>/download-link/`. Django signs a 5-minute, buyer-bound link `GET /moj-commerce/download/<entitlement_uuid>/<ticket>/`. No signed link is issued to another buyer, pending order, revoked entitlement, or blocked merchant. The storage path is generated from trusted database fields alone. Buyer can request a fresh link while quota remains.

Use `MOJ_COMMERCE_RECEIVER_ENABLED` (default false), `MOJ_COMMERCE_FULFILL_SECRET` (minimum 32 chars), `MOJ_COMMERCE_FINALIZED_TRON_CHECKER` (operator-supplied callable), and `MOJ_COMMERCE_PRIVATE_ROOT` (absolute private path). These are documented *contracts*, **not values to enable in production now**.

## How to run tests in isolated CI

```
python -m pip install 'Django>=5.2,<5.3'
python -m django makemigrations moj_commerce --check --dry-run --settings=moj_commerce.test_settings
python -m django test tests.test_moj_commerce --settings=moj_commerce.test_settings --verbosity 2
```

CI: `.github/workflows/moj-commerce-isolated-ci.yml`; source checks only, no SSH, secrets, deployment or money.

## Research inputs (verified 2026-10-21)

- [TRON official confirmation semantics](https://developers.tron.network/docs/confirmation-semantics) — broadcast success != confirmed, solidity body and receipt must be checked independently.
- [OWASP ASVS 5.0](https://asvs.owasp.org/) and [ASVS V5 File Handling](https://github.com/OWASP/ASVS/blob/master/5.0/en/0x14-V5-File-Handling.md) — authorization, private storage, strict safe names and download header policies.
- [Django `signing.dumps` / `signing.loads` max_age](https://docs.djangoproject.com/en/5.2/topics/signing/) — timestamped, revocable-in-DB buyer-only grants.
- [Django SQLite row locking limitation](https://docs.djangoproject.com/en/5.2/ref/databases/) — `select_for_update` has no effect on SQLite, hence PostgreSQL mandatory for financial production.
- [NIST SSDF SP 800-218 v1.1 final](https://csrc.nist.gov/pubs/sp/800/218/final); v1.2 published in draft, not a final standard as of the review.

## 30-day commercial validation gate

Interview 15 actual sellers and proceed to a paid pilot only if 3 evidence-backed seller commitments are secured. Start with one network (TRON), one asset (native TRX), one format (ZIP), one merchant owner with written approval. The planned USD 19 subscription and USD 99 setup fee are hypotheses, not verified revenue. Track successful delivery, manual support load, wrong-credit=0, double-grant=0, and independently verified net contribution. Do not advertise readiness from passing tests.

## Dedicated PostgreSQL concurrency gate

The isolated PR CI also starts PostgreSQL 16 to verify real row-level locking,
repeated simultaneous signed deliveries, exactly-once entitlement creation and
cross-order duplicate txid rejection. SQLite is not a valid proof of locking:
Django documents that `select_for_update` has no effect on SQLite.

```bash
MOJ_COMMERCE_TEST_POSTGRES=1 python -m django test \
  tests.test_moj_commerce_postgres --settings=moj_commerce.test_settings
```

CI's Postgres password is test-only and never used on cPanel. This remains a
synthetic proof, not an actual blockchain deposit or authorization for funds.

## v0.2 independent TRON + one-time wallet proof (2026-10-21) — isolated source

Source-only extensions, **still NOT live**:

- `moj_commerce/tron_verifier.py` implements the previously missing trusted-backend check. It fetches the **solidified** native TRX body and receipt using `mpw_tron_pro.rpc.finalized_records`, verifies the recipient and exact integer Sun using `mpw_tron_pro.core.verify_finalized_trx`, and cross-checks the signed `block_number` **and** `paid_ms` against the canonical block receipt. The API endpoint is fixed to the allowlisted mainnet TronGrid SolidityNode (no client-supplied RPC URL), and no wallet keys are used. Operator must explicitly configure `MOJ_COMMERCE_FINALIZED_TRON_CHECKER = moj_commerce.tron_verifier.independently_verify_finalized_trx` *in a privately reviewed live settings module*; the default `None` remains disabled. A single TronGrid provider is a separate read from the signed event, **not yet independent RPC-provider redundancy**. Timeouts fail safely, invoices stay unpaid.
- `moj_commerce/wallet_proof.py` adds TRON TIP-191 / `signMessageV2` seller proof-of-control with a one-use 256-bit challenge signed inside the merchant's own wallet. Message binds `mojplaywin.com`, merchant UUID, mainnet, exact public address, nonce and UTC expiration. Backend verifies Keccak-secp256k1 recovered sender using `eth-keys` / `eth-hash[pycryptodome]`, never handling a wallet private key. Invalid signature consumes the challenge; PostgreSQL locking prevents concurrent replay. Every address has a 60-second challenge cooldown and five-minute expiry. An expired/unverified address cannot take customer money. No automatic seller onboarding or KYC is implied by proving key control.
- `moj_commerce/wallet_views.py` adds authenticated/CSRF-protected seller-only endpoints; no authentication tokens in URLs, no seed collection. Both require explicit future mounting in `config/urls.py`. The Django receiver has default `MOJ_COMMERCE_REQUIRE_SIGNED_WALLET=True`; synthetic CI-only settings override it as False for legacy fake-address fixtures. Real signed proof sets `MerchantAddress.verified_via='tron-sign-v2'`.
- New migration `0002_wallet_proof.py` is source-only, not run on production database. **Do not merge or deploy this work** without owner-approved backup/rollback and operational/legal verification. All encrypted signing happens on the buyer/seller device.

**Operator security caution:** With only one API provider (TronGrid), the second read verifies data independent of the web-hook claim but not independently against a separate TRON node operator. For significant value, validate a second pinned SolidityNode provider, comparison policy and failure modes. Do not replace the verifier with test fixtures. A self-custody signed challenge proves private-key access at signing time but not legal ownership, merchant identity, multisig authorities, or future address availability.

Research: [Official TronWeb signMessageV2 + verifyMessageV2](https://tronweb.network/docu/docs/Sign%20and%20Verify%20Message/); [TronWeb sign-in with a wallet](https://tronweb.network/docu/docs/dapp/sign-in-with-tron); [TRON confirmation semantics](https://developers.tron.network/docs/confirmation-semantics); [Django DB transactions](https://docs.djangoproject.com/en/5.2/topics/db/transactions/).

### Independent cryptographic compatibility gate

An additional isolated CI job signs a **test-only** UTF-8 challenge with the official, pinned `tronweb@6.5.1` JavaScript SDK, then verifies the resulting real TronWeb V2 signature using the Python server's own Keccak/secp256k1 implementation (`tools/moj_tronweb_sign_fixture.cjs`, `tools/moj_tronweb_verify_fixture.py`). This test makes **no RPC calls and sends no funds**. It is stronger than using two Python functions based on the same assumptions. If it fails, wallet ownership must remain unapproved until the discrepancy is resolved.