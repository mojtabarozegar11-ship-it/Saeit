# F41 Merchant Crypto Export Audit Toolkit (Private Evaluation)

An executable finance-operations tool for merchants accepting TRX or TRC20 on TRON mainnet or Shasta. The product compares merchant-supplied CSV exports against issued invoices, reports missing/under/over payments, mismatched addresses/assets, duplicate transaction IDs, multi-payment allocations, and orphaned payment records. It creates deterministic evidence hashes and a reproducible integrity manifest. Python 3.11+, standard library only. No API key or wallet is needed.

IMPORTANT BOUNDARY: The tool does not connect to the blockchain, verify confirmations, prove that a payment occurred, authorize fulfillment, issue refunds, transfer money, or list/sell tokens. MATCHED_EXPORT_UNVERIFIED means only that the provided CSV rows agree. All delivery flags are false. It is not accounting/legal assurance or an independent security audit.

## Five-minute buyer evaluation

From the repository root:

    python3 -B scripts/f41_merchant_audit_cli.py \
      --invoices examples/f41-merchant-audit/invoices.csv \
      --payments examples/f41-merchant-audit/payments.csv \
      --out /tmp/f41-audit-demo

Review the invoice_review.csv, unlinked_payments.csv, report.json and integrity.json files in that private output folder. Verify that nothing changed:

    python3 -B scripts/f41_merchant_audit_cli.py \
      --invoices examples/f41-merchant-audit/invoices.csv \
      --payments examples/f41-merchant-audit/payments.csv \
      --out /tmp/f41-audit-demo --verify

The output folder must not exist when building; use a new private directory for each run. Inputs must be regular files, not symlinks. Files are limited to 2 MB each.

## CSV contracts

invoices.csv must have this exact header:

    invoice_id,network,asset,recipient,amount_base_units,token_contract

payments.csv must have this exact header:

    invoice_id,txid,network,asset,recipient,amount_base_units,token_contract

- network: exactly tron-mainnet or shasta.
- asset: TRX or TRC20. For TRX, leave token_contract blank.
- recipient and TRC20 token_contract: valid checksummed TRON Base58 addresses.
- amount_base_units: positive integer string, never a decimal or float. For TRX, one TRX = 1,000,000 SUN. For TRC20, follow the specific token contract decimals; do not assume 6 or 18 decimals.
- txid: 64 hexadecimal characters. Payment export data is untrusted and is only correlated; the chain has not been checked.
- invoice_id: 2–64 ASCII alphanumeric/_.-, beginning with a letter.

A repeated TxID causes manual-review status across every affected invoice. Different payment rows that claim the same TxID never authorize delivery. Invalid addresses and duplicate invoice IDs stop processing rather than silently fixing them.

## What a merchant receives

- invoice_review.csv — invoice-by-invoice status and recommended action.
- unlinked_payments.csv — observations without an issued invoice.
- report.json — machine-readable summaries and details.
- integrity.json — SHA-256 of inputs/outputs, NOT a digital signature or ownership proof.

## Operating policy

- Private evaluation only: no customer funds, private keys, token mint, signing, deployments, network calls, settlement or sales.
- This toolkit is deliberately isolated from MojPlayWin, cPanel production, the real MOJ1 contract and moj_1ro_1 financial actions.
- When moving beyond internal QA: independent security review, customer evaluation of a real problem, documentation of rights, separate chain-finality integration and approval of applicable commercial terms are required.
- Passing automated tests is NOT quality 1000 certification, commercial validation, or evidence of cash liquidity.

## Read-only mainnet TRON evidence (advanced private evaluation)

A second executable, f41_tron_mainnet_check.py, can query pinned TRON mainnet SolidityNode body and execution receipt endpoints. It is deliberately **off** during ordinary CSV reconciliation and does not poll or touch production site data.

Use it only with real, permissioned merchant exports containing real mainnet transaction IDs. The included synthetic example transaction IDs are NOT on-chain and cannot prove payments.

    python3 -B scripts/f41_tron_mainnet_check.py \
      --invoices path/to/real-invoices.csv \
      --payments path/to/real-payments.csv \
      --out /secure/private/new-node-evidence

- Scope: up to 10 strictly matching mainnet invoice/payment pairs per invocation; excess is rejected before any calls. Shasta entries are ineligible.
- TRX: require exact transaction ID, successful native transfer, recipient, amount, and SolidityNode solidification.
- TRC20: require an explicitly operator-approved token contract and one exact Transfer event in a successful solidified receipt, with contract, recipient, and integer base-unit amount matched.
- Token contracts default to DENIED. Set F41_MAINNET_TRC20_ALLOWLIST to up to 8 comma-separated, checksummed TRON contract addresses that your operator has independently reviewed. Never copy a token contract from an untrusted invoice into this allowlist.
- The optional F41_MAINNET_TRON_PRO_API_KEY is read as a request header but is never written to reports. This tool uses only https://api.trongrid.io; it cannot be pointed to arbitrary remote RPC servers.
- RPC errors, unavailable transactions, mismatches, duplicates and malformed event logs all fail closed. Outputs include node-response SHA-256 hashes and a private integrity manifest.
- It is evidence from ONE externally operated SolidityNode service, NOT an independent auditor, second-node consensus, guarantee against RPC compromise, or legal/financial certification.
- Passing mainnet checks still NEVER authorizes order fulfillment, customer delivery, escrow settlement, exchange listing, or sale. A separate reviewed production gate is required.

References: official TRON Developer Hub SolidityNode GetTransactionById and GetTransactionInfoById API documentation.

## Private autonomous intake (F41 only)

The private VPS install registers a once-per-minute user cron entry marked
F41_PRIVATE_INTAKE. The scheduler processes **at most three** sealed input
folders per invocation under the private runtime
operations/f41-merchant-audit/inbox/. It does not read the production database,
connect to MojPlayWin, execute a wallet, publish a listing, or deliver a product.

To submit a permitted export, create an owner-only directory named
job-<unique-id> with mode 0700, put invoices.csv and payments.csv inside
with mode 0600, then create a zero-byte READY file (mode 0600) **last**.
Never modify a READY job; submit corrections with a NEW job ID. Outputs are
written to the correspondingly named directory under outbox/ and a private
status.json distinguishes COMPLETE_READONLY from REQUIRES_REPAIR.
A job is idempotent: it will not be overwritten or silently re-run.

The worker performs offline reconciliation and—when its private runner enables
the option—read-only TRON SolidityNode queries for eligible mainnet payment
matches. It never authorizes payment settlement, file delivery, refunds,
sales, or legal attestations. A matching node response is NOT independent
commercial QC and is NOT a second-node confirmation.
If no READY jobs exist, heartbeat.json truthfully reports WAITING_FOR_INPUT.
The inbox is not connected to the site's invoice feeds; merchant-verified
exports must be supplied using this contract.
