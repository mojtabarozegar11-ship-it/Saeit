# No-RDC command route: GitHub → cPanel (pull mode)

Status: **source implementation only; NOT installed, enabled or deployed**.

## Evidence, 2026-11-10

- The official cPanel Terminal for `zomorod2` executed an ordinary shell command.
- cPanel → `https://api.github.com/` returned HTTP 200 with curl TLS verify result 0.
- cPanel → public GitHub issue 1600 comments API returned HTTP 200 with TLS verify result 0.
- GitHub-hosted runner → VPS `:22`, and runner → cPanel SSH `:1396`, remained inaccessible in the previously inspected runs. These failures do not block this *outbound* design.
- VPS command execution is **not** enabled by the cPanel puller and requires a separately verified route.

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

## Controlled installation (requires separate approval)

1. Verify code provenance, tests and ownership of the existing private
   database, HMAC key and RSA recipient key; do not print their contents.
2. Place the reviewed source in an owner-only location **outside public_html**;
   use existing Python 3.11. Do not replace the existing `company_ingress.py`.
3. Run `python3 -B zomorod_secure_issue_pull.py --probe`; this does no writes.
4. Create a one-time, mode-0600 checkpoint with `--bootstrap --checkpoint
   /home/zomorod2/.private/zomorod-business/issue_pull.state`.
5. Only after approval, use `--poll` with `--checkpoint`, `--db`, `--hmac-key`,
   `--recipient-key`, and `--ingress` pointing to existing private files. Test
   with a newly encrypted, explicitly allowlisted, non-mutating owner command,
   record the local receipt and verify the actual result.
6. Only after receipt and rollback review, add a single bounded cron entry for
   this exact command. Avoid duplicate scheduling and watch GitHub API rate limits.

Rollback: remove only the **new cron entry** after verifying its exact content.
Keep the private checkpoint and receipts for audit. Do not delete or reset
pending state on an uncertain import. Existing cPanel cron, site, database,
VPS and SSH configuration remain untouched.

## Release gates

- [x] cPanel shell command executed via official provider access.
- [x] Outbound GitHub HTTPS and owner issue feed reachable from cPanel.
- [x] Pull source is limited to encrypted owner envelope and local importer.
- [x] No-network unit tests and source read-only probe executed locally.
- [ ] Reviewed code transferred to authorized private cPanel path.
- [ ] Bootstrap checkpoint and credentials-file permissions verified.
- [ ] Fresh owner command accepted and durable receipt independently verified.
- [ ] Cron enabled and successful second-cycle operation observed.
- [ ] VPS outbound pull or another permitted command route separately proven.

No merge, deploy, paid resource, GitHub Action dispatch, hosting change, owner
message, support ticket or email is authorized by this document.
