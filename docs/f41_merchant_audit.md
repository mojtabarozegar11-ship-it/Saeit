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
