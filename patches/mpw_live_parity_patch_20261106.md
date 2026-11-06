# MojPlayWin live-parity patch — 2026-11-06

Status: PATCH-READY / NOT DEPLOYED

This patch is derived from the read-only comparison of the effective Passenger source at /home/zomorod2/Saeit-staging against PR #1965 (48bb189d5d4c2fcf047f87224249c2d986ce25e9). It must not be applied to production until the exact live file snapshot, backup, and rollback gate pass.

## Required semantic corrections

### 1. Guest privilege isolation

In `_new_user`, explicitly set `is_staff=False` and `is_superuser=False` immediately after constructing the guest model, before `save(force_insert=True)`.

After the insert/reuse check, reject any principal where either flag is true. Preserve the existing unusable-password, active-state, unique-identity, and email-ownership checks.

### 2. Custom user-model compatibility

In `_identity`, after `_read_user` returns a signed guest principal, call `_bind_guest_email` for every guest principal. Do not require a `username` attribute or hard-code the `username` field; `_read_user` is the authority for guest identity validation.

### 3. Checkout metric integrity

In `_dispatch`, count `order_start_accepted` only when the response is HTTP 302/303 and its Location exactly matches `/commerce/trx-easy/invoice/<positive integer>/`. Validation pages, store redirects, and unrelated successful responses must not increment the accepted-order metric.

### 5. Merchant activation consistency

`require_active_merchant_wallet` must reject any readiness report where `merchant_checkout_enabled` is not exactly true. A report with `WALLET_ACTIVE_REVIEW_REQUIRED` or false checkout enablement must keep new invoice issuance closed, even when RPC reachability and wallet activity flags are positive. The public catalog and direct product page must show the same paused state.

### 4. Email alias consistency

Use `request.POST.getlist()` for all supported aliases in guest binding and validate one normalized email consistently. Ignore blank legacy aliases, reject invalid values, and reject conflicting nonblank aliases.

## Safety boundary

- No checkout POST.
- No invoice creation.
- No TRX transfer.
- No email send or recovery activation.
- No database/history mutation.
- No product, price, file, or customer-data change.
- No merge or cPanel/Passenger deployment.

## Required verification before any future release

1. Compile the exact live source.
2. Run guest privilege, custom-user, email-alias, redirect-metric, download-gate, and rollback tests.
3. Verify the effective Passenger root and database.
4. Capture an independently restorable backup.
5. Apply only the reviewed source delta.
6. Verify public GET routes and unauthorized download denial.
7. Keep email and recovery gates OFF.
