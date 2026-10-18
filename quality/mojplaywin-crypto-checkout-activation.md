# MojPlayWin Native ETH/TRX Crypto Checkout — Safe Activation

Scope: **MojPlayWin primary domain only**. Never deploy this module by overwriting
shared Passenger/Django files until isolated deploy + full restore-tested backup
protects all child sites. Existing **mojplaywin-main-deploy.yml is hard stopped**;
do not bypass it.

## Included (feature-flagged, OFF by default)
- ETH Ethereum mainnet and TRX TRON mainnet **native coins only**, no token/USDT.
- Host guard, authenticated buyer and approved/published Product with active MojCryptoOffer.
- Explicit admin-set crypto price in atomic units (wei/sun); no unverified live FX.
- 30-minute, order-bound unique-amount invoice with merchant-only public wallet addresses.
- Independent read-only RPC transaction/receipt, recipient, amount, success,
  mainnet, confirmations check (12 ETH / 20 TRX by default).
- Duplicate transaction prevention; atomic order/payment-intent/ledger settlement.
- Signed-in buyer-only download **outside all public docroots**, with no URL leakage.
- No access to private keys, seed phrases, withdrawal or trading functionality.
- Native payment provider names are rejected by generic webhooks.
- Reconciliation command for previously observed, awaiting-confirmation transfers.
- Everything remains inaccessible when MOJPLAYWIN_CRYPTO_ENABLED is false.

## Necessary before enabling
1. Complete isolated host deployment and test restoring a full off-host backup. Current
   shared Django/Passenger deployment is blocked to protect child websites.
2. Apply migration 0040 on a staging clone first and pass pytest, Django checks,
   source diff and direct URL smoke tests on BOTH domains.
3. Install verified business-owned **public** receiving addresses and reliable
   chain RPC configuration only in server environment. No production secrets in GitHub.
4. Create tested digital-product files in a private, non-web-served directory,
   with access permissions restricted to the application user.
5. Have an owner review each active product, currency, legal terms, copyright,
   refund policy, delivery rights and separately defined coin atomic unit price.
6. Conduct real **small-value ETH and TRX transfers** from unrelated customer wallets,
   verify correct balance and delivered file, and negative-case tests
   (wrong chain, wrong address, wrong value, duplicate tx, late payment).
7. Implement proxy-aware abuse throttling / bot defenses for public registration
   and checkout, alerting and reconciliation scheduler before public enablement.
8. USDT is NOT supported. It needs pinned token contracts, transfer-event decoding,
   decimals, double-spend and chain verification and separate merchant acceptance.

## Merchant receiving wallets supplied 2026-10-18 (PUBLIC addresses ONLY)
Owner supplied Trust Wallet receive-screen screenshots for both native assets.
These **public receiving addresses** were transcribed and their address checks validated.
The TRON Base58Check checksum was valid and the Ethereum mixed-case EIP-55 checksum matched.
Screenshot possession **does not cryptographically prove wallet ownership**: confirm
both addresses inside the intended merchant wallet again before enabling.

- Ethereum mainnet / native ETH: `0x89149b01f59115B86553561F12438D2ADF517E75`
- TRON mainnet / native TRX: `THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73`
- TRX screenshot explicitly says no memo is required.
- Neither address accepts arbitrary coins, wrapped ETH, USDT or cross-chain transfers
  in the current checkout. **Do not send other assets or networks.**
- Do not hard-code these as production defaults or switch the feature flag on.
  Configure the corresponding environment variables on the isolated merchant
  deployment **only after** owner-side wallet comparison and restore-capable backups.

## Server-only environment variable names
```env
MOJPLAYWIN_CRYPTO_ENABLED=False
MOJPLAYWIN_ETH_ADDRESS=
MOJPLAYWIN_TRX_ADDRESS=
MOJPLAYWIN_ETH_RPC_URL=
MOJPLAYWIN_TRONGRID_API_KEY=
MOJPLAYWIN_ETH_CONFIRMATIONS=12
MOJPLAYWIN_TRX_CONFIRMATIONS=20
MOJPLAYWIN_PRIVATE_ASSET_ROOT=/path/outside/public/docroots
```

Offer prices are expressed as unsigned integer base units; example:
0.01 ETH = 10000000000000000 wei; 10 TRX = 10000000 sun.
Each invoice adds a very small unique suffix and shows the exact payable
amount prior to transfer. Do NOT activate until policy review accepts this.

Reconcile with an isolated scheduled task:
```bash
python manage.py mojplaywin_crypto_reconcile --limit 30
```
Run on the MojPlayWin isolated deployment only. The command cannot move assets.

Audit state: developed on a protected PR branch. **No live activation verified**.
