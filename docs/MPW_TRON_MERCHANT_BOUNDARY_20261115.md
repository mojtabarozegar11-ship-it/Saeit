# MojPlayWin TRON merchant boundary — 2026-11-15

This source-only contract binds a persisted TRON invoice to the exact merchant
host, merchant identifier, network, and receiver selected by a server-owned
registry.

It is deliberately not a payment activation. It performs no wallet call, RPC
probe, transaction, database migration, email, settlement, fulfillment, or
deployment. A missing or disabled registry fails closed. Apex and `www`
hosts are separate registrations; aliases are not inferred.

The receiver must also be a canonical, 34-character, Base58Check-encoded TRON-format address with prefix byte `0x41` and a valid four-byte double-SHA256
checksum. The `0x41` prefix is shared across TRON Mainnet, Shasta and Nile;
address encoding alone does not distinguish these networks. The server-owned
registry's exact `tron-mainnet` network value must be enforced separately.
Placeholder strings, whitespace, corrupted checksums and non-TRON address
formats are rejected for new invoices and persisted invoice lookups.
A syntactically valid address still does NOT prove wallet custody, economic
beneficiary, lawful acceptance, transaction finality or authorization to sell.

The contract is ready for integration into the future commercial invoice and
settlement call sites. Until those call sites, wallet custody, legal acceptance,
independent chain finality, receipt replay safety, and owner-approved runtime
settings are proven, TRON remains disabled.
