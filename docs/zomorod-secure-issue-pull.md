# No-RDC command route: GitHub → cPanel (pull mode)

Status: **installed in the private official cPanel account with a 15-minute
cron; not yet proven for a new encrypted owner command end-to-end**.

## Evidence, 2026-11-10

- The official cPanel Terminal for `zomorod2` executed an ordinary shell command.
- cPanel → `https://api.github.com/` returned HTTP 200 with curl TLS verify result 0.
- cPanel → public GitHub issue 1600 comments API returned HTTP 200 with TLS verify result 0.
- GitHub-hosted runner → VPS `:22`, and runner → cPanel SSH `:1396`, remained inaccessible in the previously inspected runs. These failures do not block this *outbound* design.
- VPS command execution is **not** enabled by the cPanel puller and requires a separately verified route.
- Live cron ran at 09:15 and 09:30 Iran time on 2026-11-10. Both runs returned
  `ISSUE_PULL=NO_NEW_AUTHORIZED_COMMAND`. One matching cron line exists and
  all 41 older entries were preserved.
- Live script SHA256 after the receipt fix:
  `a4611d784074bd94c58b330f5e4d4490d373cb6350de9525b97b86986b027900`.
  The old version was backed up as `.issue-pull.before-receipt-fix-20261110.py`.
  Both `COMMAND_RECEIPT=ACCEPTED` and `COMMAND_QUEUE=UPDATED` are now
  required from the private importer's real multi-line output.

## Trust and operation

`scripts/zomorod_secure_issue_pull.py` uses Python 3.11 standard library only.
It performs a verified HTTPS GET of the *existing public* owner inbox
(`mojtabarozegar11-ship-it/Saeit#1600`), checks the fixed GitHub account ID,
login, OWNER association and unedited message, validates the encrypted envelope
shape, and passes **at most one** envelope to the already installed private
`company_ingress.py`. The importer alone decrypts and enforces its task policy.

No arbitrary shell text from GitHub is executed. The importer signs its local
task record with its private HMAC key. Public issue comments reveal metadata and
ciphertext to the public; use this transport only while encryption and key
rotation remain enforced. Do not place plaintext, passwords, SSH private keys,
cookies or tokens in issue comments or public logs.

The first bootstrap deliberately records the highest existing comment ID and
does not execute historical commands. On subsequent polling, a locked, private
checkpoint records a pending ID/hash **before** the importer runs. A crash or
uncertain result leaves the poller blocked pending reconciliation: do not delete
the checkpoint to force retry. Key rotation after acceptance means only one
encrypted command can be accepted per poll. Run a second poll only after the
sender has obtained the current recipient key and encrypted a new command.

## Offline sender: prepare, but do not post, an owner command

`scripts/zomorod_seal_owner_task.py` requires only the current **public**
RSA-3072 key, an allowlisted task JSON file and installed OpenSSL. It never
contacts GitHub, sends a message or changes the live server.

1. In the official cPanel Terminal, use the private ingress
   `show-public-key` operation with its approved private path arguments to
   export **only the public PEM**. Do not reveal or copy the HMAC key, private
   RSA key, database, session cookies or owner passwords. At audit time the
   public DER SHA256 fingerprint was
   `edad32677afef00b84089f278d559e225af04a6f520da201be5aee50c90a1795`.
2. Store the retrieved key as `current-recipient-public.pem` in the
   authorized producer's workspace. It becomes stale after *one accepted*
   command because the recipient rotates its RSA key.
3. Put the owner-authorized task in `owner-task.json`, with exactly these
   seven fields:

   ```json
   {
     "workstream": "operations",
     "priority": "high",
     "risk": "read_only",
     "title": "Audit owner task intake",
     "detail": "Inspect the command center without modifying business data.",
     "deliverable": "Evidence-backed audit summary",
     "acceptance": "No data changes and an attributable report"
   }
   ```

4. Encrypt offline:

   ```sh
   python3 scripts/zomorod_seal_owner_task.py --public-key current-recipient-public.pem --task-file owner-task.json --output sealed-comment.txt
   ```

5. The output is created with mode 0600 and cannot overwrite another file.
   Its first line is `ZMR-SEALED-COMMAND-V1` followed by authenticated
   ciphertext. A newly authorized GitHub Issue #1600 comment from the
   exact pinned owner account is the eventual intake route; **this procedure
   does not authorize or automatically perform that posting**.
6. Retrieve the next public key *after each successful import*; never reuse
   an old ciphertext or public key.

The sender generates independent AES-256 and HMAC-SHA256 keys, wraps them using
RSA-OAEP-SHA256, encrypts the task with AES-256-CBC and a random IV, then
authenticates the protocol magic, wrapped key, IV and ciphertext. Tests perform
an independent OpenSSL decrypt/verify round-trip without live commands.

## Installation record and change control

1. Verify code provenance, tests and ownership of the existing private
   database, HMAC key and RSA recipient key; do not print their contents.
2. Place the reviewed source in an owner-only location **outside public_html**;
   use existing Python 3.11. Do not replace the existing `company_ingress.py`.
3. Run `python3 -B zomorod_secure_issue_pull.py --probe`; this does no writes.
4. Create a one-time, mode-0600 checkpoint with `--bootstrap --checkpoint
   /home/zomorod2/.private/zomorod-business/issue_pull.state`.
5. Live `--poll` uses reviewed private file paths. The first freshly
   authorized encrypted task and its independently verified database receipt
   remain **unproven**.
6. Exactly one cron entry now runs every 15 minutes; its owner-only
   `issue_pull.log` and the saved `.issue-pull-cron.before-20261110` have mode
   0600. Successful second time-slot operation has been observed.

Rollback: remove only the **new cron entry** after verifying its exact content.
Keep the private checkpoint and receipts for audit. Do not delete or reset
pending state on an uncertain import. Existing cPanel cron, site, database,
VPS and SSH configuration remain untouched.

## Release gates

- [x] cPanel shell command executed via official provider access.
- [x] Outbound GitHub HTTPS and owner issue feed reachable from cPanel.
- [x] Pull source is limited to encrypted owner envelope and local importer.
- [x] No-network unit tests and source read-only probe executed locally.
- [x] Reviewed code transferred to authorized private cPanel path.
- [x] Bootstrap checkpoint and credentials-file permissions verified.
- [ ] Fresh owner command accepted and durable receipt independently verified.
- [x] Cron enabled and successful second-cycle operation observed.
- [x] Private ingress receipt mismatch corrected and tested.
- [x] Offline encryption producer verified with independent OpenSSL round-trip.
- [ ] VPS outbound pull or another permitted command route separately proven.

No merge, paid resource, GitHub Action dispatch, VPS change, outgoing GitHub
comment, support ticket or email is authorized by this document.
