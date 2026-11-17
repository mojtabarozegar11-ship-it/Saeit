# Factory: private Google Drive A+B OAuth on owner-runner — exact operational gate

**Status (17 Nov 2026):** the official `rclone v1.76.0` binary was acquired, SHA-256 pinned, version-tested and removed automatically on the owner runner in a read-only GitHub job. Neither owner-local `rclone.conf` nor two rclone remotes were found at prior inspection. This is **NOT** a current backup or authorization to dump any database.

## Verified official technical requirements

- 2026 rclone Google Drive docs warn that the shared default Google OAuth `client_id` is being retired. **Use the owner's own Google Cloud OAuth Client ID**, if available, for a stable long-lived connection; do not assume the shared default will work. Google Cloud project creation is not permission to activate billing; no fees/paid services are authorized.
- This runner has NO transferable OAuth from ChatGPT's separately connected Drive plugin. Token extraction from the ChatGPT plugin is not a supported solution.
- The owner must approve the Google sign-in/consent **separately for A and B**. Run OAuth only in a trusted local browser/device and transfer its token **directly to an owner-controlled shell/config**, never into ChatGPT, email, PR text, GitHub Actions artifacts or logs.
- Both destinations need independent private Drive accounts, and `root_folder_id` must be the exact independent folders already verified:
  - A `191sAkv4A01S9o6zhx-vM5xM7WO31qHPn` (account A)
  - B `1e6D3Ek4k-4JT_oyEoiY_JejErZFssrC_` (account B)
- Use owner-local config (`~/.config/rclone/rclone.conf`) chmod **0600**, no symlink, owned by the invoking OS user. Never install to system/global directories or open an rclone RC server. The `rclone` executable can instead be obtained for a single invocation using the hash-pinned Python context manager in `scripts/factory_rclone_ephemeral_binary.py`; no permanent OS install is required.

## Safe one-time owner-authorized setup (requires interactive sign-in)

1. In an authenticated owner-controlled shell on the **authorized runner**, ensure `umask 077`, a private home directory, and an explicit owner-only `rclone.conf` path. No commands should reveal tokens or whole config.
2. Use the officially downloaded and SHA-pinned `rclone` binary (the exact release digest is in the source) inside the temporary context. The user approves two Drive OAuth connections under **different Google identities** using the official rclone setup / headless flow on a trusted device. Do not enter tokens in chat or command line arguments visible to process listings.
3. Set the two remotes' `type=drive` and correct `root_folder_id` in private config, with distinct OAuth grants. Do **not** create sharing links or give nonowner access to existing private backups.
4. In the same trusted owner process only, run `rclone about --json remote_a:` and `remote_b:`; record only `total`, `used`, `free` byte counts in a nonsecret attestation. If free bytes are not exposed by both providers, **HOLD**. Source compressed size estimate + per-part overhead + 1 GiB reserve must be supported independently by **each** account.
5. Confirm each remote can read its own private `F-01 Factory VPS encrypted recovery 2026-10-30/manifest.json` and that SHA-256 is `753365e1584a228d4a4b60b1f7bc21dabdf9514dfc1fe362b5257326768233da` before any new write. Never sync/delete historical F01.
6. Import the context manager as `with provision_verified_rclone(Path(os.environ['RUNNER_TEMP'])) as exe:` and pass `rclone_exe=str(exe)` into `RcloneDualStore` so the binary exists throughout preflight and transfer and is cleaned on exit. No separate persistent binary installation needed.
7. **HOLD** until production Passenger's exact MySQL database identity and full app/media/subdomain inventory are proven, and an isolated restore environment has adequate capacity. All 101 InnoDB tables observed earlier were from staging and do **not** prove which live worker schema is active.
8. Only when all gates pass: one coherent SQL dump + complete app/media snapshot, compressed once, encrypted into at-most-8 MiB GCM parts; upload to both roots, read back SHA-256 for **all** parts and final manifest LAST. After that independently restore current MariaDB plus Django in isolation and verify functionality with outbound payments/emails/trading disabled.

## Strict NO-GO if any prerequisite fails

Do not upload plaintext, install system packages with sudo, write credentials to Actions/GitHub, expand billing, open remote-control services, fill the VPS disk, flip old workflows' `if: false`, stage a full local SQL backup, overwrite the F01 historical backup, or report `2/2` for current data without independently verified complete and restorable copies.

Official docs: https://rclone.org/drive/ ; https://rclone.org/commands/rclone_about/ ; https://rclone.org/remote_setup/ ; https://rclone.org/release_signing/ .
