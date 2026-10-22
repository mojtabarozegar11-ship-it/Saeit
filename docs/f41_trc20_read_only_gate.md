# F41 Shasta TRC20 private merchant reconciliation (read-only)

The F41 product factory runs reconciliation jobs from the existing authenticated `moj_1ro_1` queue. This module independently checks **Shasta testnet** token transfers, using the SolidityNode **transaction body and finalized execution receipt**.

## New optional invoice shape

A `TRX` invoice remains unchanged. A `TRC20` invoice must include `token_contract`, a Base58Check Shasta contract address. All other fields remain as in `factory_config/f41_samples/reconciliation.json`.

```json
{
  "id": "invoice1",
  "network": "shasta",
  "asset": "TRC20",
  "recipient": "TWTBsKZPVuQgaGNbyJWJm9XR28g4wVBCNQ",
  "amount_base_units": "1000000",
  "token_contract": "<real-approved-Shasta-token-contract-Base58Check>"
}
```

The placeholder above is a reminder, **not** an executable contract address. Observations retain their old fields, including the on-chain `txid`; user-supplied `node_receipt_sha256` never substitutes for independent verification. No number of decimals is assumed: the amount is **raw token base units**.

For explicit operator authorization, the existing 15-minute cron may inherit `F41_SHASTA_TRC20_ALLOWLIST`, a comma-separated list of at most eight reviewed real Shasta token contract addresses. Default is empty; without a valid allowlist the verifier returns `TRC20_CONTRACT_NOT_APPROVED` and does **not** query a TRC20 receipt. Do not approve contracts based solely on customer claims or ticker symbols such as USDT. This gate does not prove code quality or economic value of any listed token.

## Fail-closed proofs

For each eligible private queued order, the sidecar:

1. Confirms the transaction body on `/walletsolidity/gettransactionbyid`, with exact transaction ID, successful `TriggerSmartContract`, and a single outer contract invocation.
2. Confirms matching finalized receipt on `/walletsolidity/gettransactioninfobyid`, positive block height, and `receipt.result=SUCCESS`.
3. Finds **exactly one** `Transfer(address,address,uint256)` log emitted by the explicitly allowlisted contract; its recipient and amount must match the order. Ambiguous, missing, reverted, mismatched, malformed and unavailable receipts fail closed.
4. Hashes the result into the existing private evidence folder, with original request hash. No signature, mainnet RPC, wallet key, broadcast, order payment status mutation, sale, or customer delivery occurs.

One TRX observation costs at most one Shasta query. One TRC20 observation costs at most two. Per-cycle scanning reserves at most **eight** RPC calls, so worst-case network timeout is bounded at 80 seconds on the existing 15-minute cron.

## Business readiness: still unverified

This upgrade increases technical **candidate** utility; it does not create paid buyers, real cash liquidity, approvals, audits, or market price. Use genuine test transactions and separately review the token code, buyer ownership, regulatory duties, and your payment/delivery integration before ever enabling sales.

Official protocol references:
- https://developers.tron.network/docs/confirmation-semantics
- https://developers.tron.network/docs/exchangewallet-integrate-with-the-tron-network
- https://developers.tron.network/docs/event
