# Starter30 — safe single-owner-wallet invoice signature release contract

**Status:** source-only. This document is a mandatory release contract, not evidence of production readiness.

## Hard boundaries
- Exactly one owner-approved receive-only TRON address. No alternative receiving wallets, shared reserve wallet, test payees, hardcoded secrets or automatic sweeping.
- Exactly **30 native TRX = 30,000,000 SUN**, TRON mainnet, only for a server-issued Starter30 invoice. No unique dust amount or unverified deposit.
- Challenge and simulated account stages (eventual progression up to the marketed virtual limits) use **simulation balances**, not live funded broker accounts; performance payouts, when earned, are real company obligations and must remain separately funded and legally reviewed.
- Never solicit seed phrases, private keys or password / signing device custody.

## Trust boundaries
1. Verify buyer's email with existing short-lived OTP; create at most one accountable pending invoice per legitimate buyer session under a dedicated isolated MariaDB transaction.
2. Record an immutable invoice: identity digest, terms hash, allowed sender address, sole receiver, 30 TRX, network, issued/expiry and state.
3. Server generates a random 32-byte nonce, HMAC/Django-signed ticket and canonical literal plaintext covering invoice ID, buyer identity digest, payer, receiver, amount/network, legal terms and official origin; return ticket and message.
4. Buyer optionally connects a compatible TRON signing wallet (e.g. TronLink, `trx.signMessageV2`) for **message signing only, not a TRX transfer**. Warn that exchanges may not offer this function.
5. **A trusted server verifier**, e.g. pinned TronWeb `Trx.verifyMessageV2(message, signature)`, recovers the TRON Base58 signer from the raw signed message; server compares it against invoice sender. The browser cannot send an unverified yes/no token.
6. After successful signature recovery, atomically insert/claim a nonce hash in *shared durable MariaDB* under a **unique nonce constraint**, bound to the invoice and identity, for no longer than 10 minutes; collision / timeout / verifier unavailability = HOLD, never PAID.
7. Concurrency: serialize invoice authorization per verified identity+sender. Reject any second active overlapping invoice for the same sender/owner-recipient unless both are directly resolved with authenticated wallet control and verified unique correlation. Never let public TXID alone choose an invoice owner.
8. Only thereafter give the buyer an invoice with the exact receiver and amount; complete transfer in user's own wallet. Two *independent* TRON solidity providers verify finalized network, native TRX transfer contract, on-chain sender, receiver, 30,000,000 SUN, transaction success and block-time validity.
9. Within isolated DB atomic transaction, lock invoice and enforce one unique global TXID, matching source wallet proof and no competing prior claimed transfer; only then assign account, mark PAID, publish unique receipt and download credentials.
10. Exchange/custodial wallet unable to sign: support evidence-led **human review** with strict no-automatic-entitlement policy and customer-safe instruction *not to send* before buyer's feasible reconciliation route is accepted. Never falsely promise walletless automated proof.
11. Preserve all old paid/expired invoices and recovery procedures. No backfill or rewriting historical evidence; any new required proof applies prospectively after compatible migration.
12. Restore/test backup and check exact production source-bundle parity, independent finance reserve proof, SMTP deliverability and safe worker reload on controlled production release. No one should declare financial go-live from release flags alone.

## Evidence gates
- Server cryptographic recovery not client JS; independently verified v2 input string. Never mix legacy `verifyMessage` with v2 `signMessageV2`.
- Unique index across nonce hash and across network+txid; prove concurrent claim under MariaDB.
- Automated negative tests: stolen public TXID, fake sender text, wrong signer, cross-invoice and cross-email, modified site/chain/price/recipient, expired ticket, replays, concurrent buyers, payment after expiry, historical invoice recovery, exchange sender manual hold, network-provider disagree, missing reserve proof.
- Explicit dynamic buyer state machine: EMAIL_VERIFIED → WALLET_PROVED → INVOICE_READY → CHAIN_FINAL → PAID → SIM_ACCOUNT_DELIVERED, with separate MANUAL_REVIEW and EXPIRED paths.
- No secret, customer raw email, raw IP, private seed or unmasked wallet set in public logs/GitHub. Use audited production-only config.

### Technical source
- `prop_firm/starter30_wallet_proof_contract.py` contains the canonical challenge/verification interface; fail-closed until trusted verifier and durable claim adapter are implemented.
- `prop_firm/starter30_payer_claim_guard.py` is the separate conservative collision-query helper already merged; **not integrated** into live settlement.
- `prop_firm/starter30_live.py` and the 12-file pinned bundle MUST NOT change until all finance release tests, backup/restore and backward-compatibility controls are proven.

Official docs:
- https://docs.tronlink.org/dapp/message-signing/
- https://tronweb.network/docu/docs/dapp/sign-in-with-tron
- https://tronweb.network/docu/docs/6.1.0/API%20List/trx/verifyMessageV2

No deployment/financial release claimed.
