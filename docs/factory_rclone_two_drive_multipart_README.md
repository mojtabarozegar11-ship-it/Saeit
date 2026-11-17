# Factory current-data backup: bounded encrypted parts to TWO owner Drive accounts

**Status:** audited transport implementation and offline suite only. **No current factory SQL/app/media bytes have been transferred by this code.** The preceding historical 2026-10-30 F01 two-Drive archive remains intact and independently file-tree restorable. No live restore/deploy/payment is authorized.

## What this actually solves

The preexisting `scripts/factory_dual_stream_v2.py` (draft PR #2680) already encrypts one binary source stream in independently authenticated AES-256-GCM parts (4 MiB default, maximum 8 MiB) with a fresh 128-bit run ID, per-part hashes and RSA-OAEP-wrapped AES key. It requires independent upload/read-back callbacks. `scripts/factory_rclone_dual_parts.py` supplies those callbacks against the **two owner's privately owned Drive folders** with `rclone rcat` and `rclone cat`. It also supplies a guarded `VerifiedGzipSource` that checks **both** the source producer's and gzip's exit codes before returning EOF to the core, avoiding a false *complete* manifest after partial SQL output.

**Splitting saves VPS disk scratch space; it DOES NOT reduce cloud quota consumption.** Do not attempt a 16.68 GB raw export unless measured compressed bound plus ciphertext overhead plus reserve fits **each** destination independently. This design uses bounded process memory, not a large temporary SQL/gzip file. Existing client/site data remains on the source server. The current baseline remains **0/2 complete new current backups**.

## Destination identity and explicit authorization (mandatory)

The owner must separately set up two official rclone Google Drive OAuth connections **on the existing owner-controlled backup runner**, not with ChatGPT's separate Google Drive connector. No access/refresh token, local config, private recovery PEM/passphrase or DB credential may be put in chat, a GitHub commit, Actions logs, or a public URL.

Expected *different*, existing, owner-verified **private** destination root-folder IDs (root folder configuration, not an API bearer token):

| Target | Owner-account identity verified previously by Google Drive connector | Expected private Drive `root_folder_id` |
|---|---|---|
| A | `mojtaba.rozegar11@gmail.com` | `191sAkv4A01S9o6zhx-vM5xM7WO31qHPn` |
| B | `mjtbyrwzgar058@gmail.com` | `1e6D3Ek4k-4JT_oyEoiY_JejErZFssrC_` |

Owner's `rclone.conf` must be 0600, owned by the executing OS user, NOT a symlink. The two remotes must be distinct Google Drive OAuth tokens (`type = drive`) with the exact independent `root_folder_id` values above. The program does not print or return tokens. Before upload the program separately reads the existing PRIVATE proof object inside both accounts:

`F-01 Factory VPS encrypted recovery 2026-10-30/manifest.json`

Expected proven SHA-256: `753365e1584a228d4a4b60b1f7bc21dabdf9514dfc1fe362b5257326768233da`. Because both roots are owner-private and unshared, being able to read **both exact roots** plus an independent token is evidence for distinct provider access. If proof absent/mismatched, abort. No new sharing permissions should be created.

Read provider quota via separate `rclone about --json remote_a:` and `remote_b:` (not a filesystem `df`). A/b unknown free bytes, insufficient free bytes, missing rclone, missing OAuth, wrong root, shared OAuth token or a connection failure **HOLD BEFORE ANY SOURCE READ**. This code verifies configured root and proof; it does not independently query the Google account email, so the original connector account ownership audit remains a prerequisite.

## Transfer algorithm

1. **Prerequisite**: independently verify actual active Passenger worker's DB binding, current full source+media/subsites, routine/trigger/event coverage, approved consistency/DDL window, owner-held correct public/private key pair, and independent restore capacity. The previous C169 inspection proves only staged WSGI *source* settings: active worker/complete media scope still **UNPROVEN**. Do NOT make up a DB name or infer all app data is in a single schema.
2. **Prerequisite**: a trusted owner-supplied `vetted_producer_argv` that creates a single consistent snapshot of that approved live MariaDB database using `--single-transaction --quick --routines --triggers --events`, with appropriate read-only DB credentials and without concurrent DDL. This low-level module deliberately DOES NOT generate or execute a guessed production DB command by itself. It has no auto-start of customer data acquisition. Generic commands passed by an untrusted party must NOT be executed.
3. The operator calls `RcloneDualStore(...).preflight()` BEFORE opening the source. It authenticates both remotes' private proof file, checks `rclone about` free bytes vs the EXPLICIT `max_source_bytes` bound, AEAD overhead and reserve (suggest at least 1 GiB per account). If required capacity cannot be proven, **do not read/transfer source**.
4. Use the existing validated cryptography core, supplying `RcloneDualStore.callbacks('factory-current-<fresh random 32 hex>')`, plus a **fresh** 128-bit run namespace. `VerifiedGzipSource` produces compressed bytes from exactly one producer process, checking upstream and compressor exit status before signaling EOF. `encrypt_verified_pipe_to_two_owner_drives(...)` wraps both into one callable after preflight. It **never** infers consistency from a zero process exit; source-identity and live consistency gates are separate.
5. For every part: `rclone rcat` uploads the already encrypted payload to **A** and **B** under a new unique namespace; `rclone cat --head` downloads bounded bytes; the existing F01V2 engine compares exact length+SHA-256 and authenticates the manifest. Each part <= 8 MiB + small AEAD header/tag, so no large staging files. No `rclone sync`, removal or overwrite of historical backup roots. The random namespace prevents accidental reuse; Google Drive itself does not provide an atomic no-overwrite guarantee for `rcat`, so do not reuse an earlier namespace.
6. If **either** producer, gzip, owner proof, quota, upload or readback fails, abort: **NO completion manifest published** (incomplete orphan ciphertext might remain; NEVER delete automatically). Only after source, compression, both destinations and all part reads succeed is the authenticated completion manifest written LAST to both remotes.
7. Retrieve all parts independently from **each** Drive; restore under isolated capacity/ownership permissions; verify manifest MAC, GCM, exact bytes, SQL schema/data and Django application/media behavior with external email/markets/payment integrations disabled. Only then classify the **CURRENT** backup as independently restorable. An uploaded manifest alone is not restore proof.

## Actual code and bounded tests

```text
PYTHONPATH=scripts python3 -B -m unittest -q tests.test_factory_rclone_dual_parts
python3 -B scripts/factory_rclone_dual_parts.py
```

The default `__main__` command is **read-only, offline** and outputs only `rclone_installed` and `owner_local_config_secure_file_present` booleans; does NOT read OAuth configuration contents or call a remote provider. This can safely run on the existing self-hosted factory runner to determine whether setup is even present. Unit tests use a dummy in-memory Drive backend and isolated one-shot local source processes; no real Google Drive account or production SQL is touched.

This change is to be stacked on top of existing **draft PR #2680**, not silently merged into main or deployed. Old SQL workflows with job `if: false` remain disabled. No new paid provider, token purchase, DB export, customer email, overwrite, or archival deletion is part of this PR.

## Critical remaining blockers

- Source: active Passenger DB instance, full app/media/subdomains inventory, DDL-consistent capture: **not verified**.
- Transport: actual `rclone` installed + two owner-authorized server-side OAuth remotes, provider-confirmed free bytes: **unknown** until the runner preflight completes.
- Recovery: independent, full current DB+app/media service restore in safe nonproduction environment: **not performed**.
- Current complete backup copies: **0/2**. Historical F01 archive is not current data.

### Crash/retry isolation hardening (17 Nov 2026)

Before creating any `factory-current-<128-bit-hex>` run folder, the provider
adapter now demands bounded `rclone lsf` listings of the preprovisioned
`current-backups` parent in **both** independent private Drive accounts. Any
existing matching namespace (case insensitive), listing error, malformed
listing, or nonempty just-created run folder **HOLDs before any ciphertext
upload**. A transport object cannot start two backup runs. A failure leaving
orphan encrypted parts must be investigated; restarting with the same run ID
is deliberately denied. Do not delete orphan bytes automatically. This
is a race-resistance safeguard, **not an atomic create-if-absent guarantee on
Google Drive**, and it does not replace official provider quota/consistency
admission. Both `current-backups` parent folders have been created privately
and independently: A folder `10CwlKyd_I3iaiCVbdH82IbzVJD_8z475`, B folder
`1EXF8_gl5xZDQBjnrcOVxd_rdznLAj78j`; both verified empty at creation.


## Enforced manifest-order admission (2026-11-17, hardening review)

The transport callbacks now record the exact ciphertext SHA-256 and length of
EVERY successful per-provider uploaded part and independently confirm its
bounded provider readback. Even if an unrelated caller invokes the low-level
callbacks outside the core's correct ordering, **neither provider is allowed to
receive a completion manifest until both provider part sets are nonempty,
identical, and every part has been independently read back**. A mismatched
provider blob fails closed and is not credited. Different manifest object names
are rejected; no ciphertext part may be appended once either manifest starts.
These additional checks are defense in depth and do NOT cryptographically
validate the manifest: the core's authenticated MAC and offline decrypt are still
mandatory. Provider rcat does not implement atomic no-overwrite; the fresh
one-time run namespace remains mandatory. Nine independent adversarial cases
were added (55 total); source-only CI run must pass before treating the
candidate as reviewed. No live backup or cloud credential change is authorized.


## Terminal manifest inventory binding (additional hardening)

The provider adapter now also checks the **canonical F01V2 JSON manifest** before
issuing either remote terminal-object write. It rejects duplicate keys,
noncanonical byte encodings, unexpected fields, invalid run and part names,
noncontiguous part indexes, unaccounted objects, wrong per-part SHA256/length,
incorrect ciphertext/plain totals, an invalid number of owner pseudonyms,
claiming that restore/source consistency was already verified, and divergent
A/B terminal manifests. Both provider **manifest readbacks** must also match
exact submitted bytes. This is defense in depth for accidental low-level
callback misuse; it never substitutes for the manifest's secret-key MAC,
per-chunk AES-GCM authentication, or an isolated full current restore.

All checks run without revealing OAuth tokens or filenames from the live
factory. Neither side is marked as having a complete **current** backup merely
because the structural manifest passed. The source is still staged in a Draft
PR; production backups remain forbidden until source identity, owner OAuth,
provider storage quotas and independent key recovery are proven.
