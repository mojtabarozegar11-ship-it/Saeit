# MOJ1 Shasta disposable reward pilot — manual handoff (draft)

**NO-GO for public rewards and Mainnet.** This package only prepares two disposable Shasta contracts.
It does not mint, transfer or release guarded MOJ1 V2 reserves; `MojRewardTestToken` is named
"Disposable reward test" (TTEST) and has **no financial value**.

## Boundary
- New manual entry point: `scripts/deploy-reward-shasta-manual.mjs`.
- Creates a disposable TTEST token first, then `MojRewardClaimsPilot` whose token is **TTEST**,
  not `MojCoinGuarded`. Governor must match the recorded guarded V2 Shasta pilot governor.
- The protected MOJ1 V2 genesis distribution stays disabled. This installer never calls
  `distribute`, `publishEpoch`, `approve`, `execute`, `claim`, `transfer` or other payout.
- CI runs **only** syntax, mocked/offline policy, journal and compile tests. CI does not load any
  private key or invoke the manual installer.
- The earlier `scripts/deploy-shasta.mjs` is for a separate token/NFT V1 experiment,
  and must not be reused as the reward deployment entry point.

## Conditions before any manual signing
1. Owner separately approves this Shasta-only experiment, a named disposable signer public
   address, the three already-verified independent Shasta governor public addresses and
   an explicit per-contract `feeLimitSun` (10–1000 **test** TRX). For two contracts, the
   account must be able to cover two complete fee ceilings; no Mainnet TRX.
2. Use a dedicated Shasta-only key controlled in a private operator session. **Never** paste a
   private key, recovery phrase or signing payload into ChatGPT, GitHub Issues, Actions,
   a repository, email or a screenshot. Never repurpose an existing Trust Wallet / Mainnet key.
3. Compile the *pinned* source. Confirm `MOJ1_REWARD_SHASTA_OPERATOR` is the dedicated
   test-wallet public address, `MOJ1_REWARD_SHASTA_GOVERNANCE` matches the V2 Shasta
   manifest, and `MOJ1_REWARD_SHASTA_GOV_OWNERS` lists three distinct governor owners in
   on-chain index order. An unresolved owner/nonce mismatch stops the run.
4. Use a new **private absolute persistent** `MOJ1_REWARD_SHASTA_JOURNAL_PATH` outside
   the repository and temporary directories. Configure the following **only in the private
   operator session**, after owner approval:

   - `MOJ1_REWARD_SHASTA_CONFIRM=SHASTA_DISPOSABLE_REWARD_ONLY`
   - `MOJ1_REWARD_SHASTA_DEDICATED_WALLET=NO_MAINNET_FUNDS_OR_KEYS`
   - `MOJ1_REWARD_SHASTA_OPERATOR` (public)
   - `MOJ1_REWARD_SHASTA_GOVERNANCE` (public)
   - `MOJ1_REWARD_SHASTA_GOV_OWNERS` (three comma-separated public addresses)
   - `MOJ1_REWARD_SHASTA_FEE_LIMIT_SUN` (decimal sun)
   - `MOJ1_REWARD_SHASTA_JOURNAL_PATH`
   - `MOJ1_SHASTA_DISPOSABLE_PRIVATE_KEY` (**private operator session only**)

5. Only then manually run `node scripts/deploy-reward-shasta-manual.mjs`.
   It journals txID and raw transaction fingerprint before a **single** Shasta broadcast
   attempt. If interrupted or RPC uncertain, **never redeploy automatically**.
   Compile the same artifacts and run `node scripts/reconcile-reward-shasta.mjs`
   without a key to recover the existing journal; preserve it even after errors.

## Acceptance evidence
- Two distinct testnet deployment txIDs, success receipts, bytecode hashes and addresses.
- Token on-chain name exactly "Disposable reward test", symbol exactly "TTEST",
  expected test supply, and escrow token/governance getters match the approved inputs.
- New escrow initially has zero outstanding liabilities and zero available funds.
- Separate governance signing, synthetic prefunding, epoch publication, proof claims
  and negative tests **have not run** as part of this stage.
- Independent auditor, entitlement policy, anti-Sybil/identity evidence, legal review
  and explicit real-token governance approval remain mandatory gates.

Tracker: https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1077 .
