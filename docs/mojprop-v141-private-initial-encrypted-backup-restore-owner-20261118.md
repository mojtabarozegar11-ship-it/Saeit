# MOJ PROP — first independent zero-customer SQLite backup

**Scope**: The initial `merchant-initial-snapshot.sqlite3`, made before any paid orders. This is not the current MariaDB, not a complete MojPlayWin deployment, and not customer data.

## Verified real original, 18 November 2026

[Actual owner VPS run #44248174012](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44248174012) passed pinned recovery public key validation, fixed incompatible legacy `cryptography` backend loader, and copied real source over read-only SSH:

| Evidence | Exact result |
|---|---|
| cPanel initial private SQLite source | 446,464 bytes |
| SQLite source SHA256 | `c10113de0442f170121f36a37192a2337e47fff1d3b6636681d2246e73685f82` |
| AES256-GCM ciphertext | 13,788 bytes |
| RSA-wrapped encrypted ZIP, held owner-private on VPS | **15,545 bytes** |
| Encrypted ZIP SHA256 | `e7b5f860c7cfbe221928d5c8b863fb905119339deb819ffba90cfb8b49f69e2f` |
| Recipient public key fingerprint | `a7b3ef1995681d3963d56570ce68b2c4cf9785e99163f66795592cb907632d74` |
| In-memory AES-GCM restore and isolated SQLite integrity check | PASS |
| Owner private key used on VPS | NO |
| Live production access / factory restart | NO |
| New MariaDB / current customer backup | NO |

## Two-owner Google Drive transport format (ONLY initial zero-customer source)

The encrypted-only transfer script `scripts/mojprop_v141_owner_encrypted_log_bridge_20261118.py` reads exactly one owner-private 15,545-byte ZIP from the owner runner. It verifies **SHA256 of the actual file**, ciphertext member, expected source identity and RSA recipient, then emits a canonical 20,728-character Base64 encoding in three bounded 7,000-character sections.

GitHub Actions logs are public and are **an untrusted carrier of ciphertext only**. The carrier MUST NOT include private-key bytes, passphrases, plain SQLite data, sensitive logs, customer records, KYC or balances. The purpose is to place two independent **PRIVATE** owner-held Google Docs into distinct accounts; the Google Docs must be byte-verified after writing. A Google Doc is not a native binary ZIP: it stores a losslessly recoverable Base64 form of the ZIP. Label it accordingly. Zero cost requires no GitHub artifact, no external paid hosting, no paid API, no billing change.

The documents use two unique markers:
```text
MOJPROP_ZERO_CUSTOMER_BASE64_BEGIN
<3 lines of Base64 ASCII; 20,728 characters total>
MOJPROP_ZERO_CUSTOMER_BASE64_END
```
Do not treat a Google Doc missing either marker or failing exact SHA256 as a backup.

## Owner restore, offline only

1. On an isolated computer owned by the user, export one of the **private** Google Docs to an encrypted-media or owner-only `.txt` file. Confirm SHA and customer-scope before continuing.
2. Use `chmod 600` for the private exported text file and the owner recovery key. Create a `0700` destination directory that is NOT inside any public site or production project.
3. Run the approved code `scripts/mojprop_v141_private_drive_doc_base64_zip_restore_20261118.py --input /OWNER/private/export.txt --output /OWNER/private/restore/new-encrypted.zip`. The tool validates all 15,545 bytes, SHA, exact ZIP content and pinned public key; it **refuses to overwrite existing files**.
4. The separate `scripts/mojprop_v141_owner_isolated_rsa_recovery_20261118.py --package /OWNER/private/restore/new-encrypted.zip --private-key /OWNER/private/factory_recovery_private_20261030(1).pem --password-file /OWNER/private/owner-password.txt` performs RSA-OAEP/AES-256-GCM decryption and integrity checks, without writing unencrypted output unless explicitly instructed to create a new isolated file.
5. Only the correct owner private key (distinct from the incompatible legacy filename without `(1)`) may be used. No one should upload that private key or its password into GitHub/Google Drive/logs.

**Release gates:** This validates a zero-customer initial ledger backup only. It does not authorize any real 30 TRX checkout, customer onboarding, deletion, live service restart, archive cleanup, or production database restore. Full current MariaDB + application + media remains a separate necessary backup and recovery project.
