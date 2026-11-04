# F-01: private state checkpoint and fail-closed recovery

Status: **draft / not authorized for live VPS activation**.

## Scope and invariants

- One active product: `farm_enterprise_economics`; no next SKU or publication.
- This checkpoint covers the isolated SQLite database and all regular files
  within `private/autonomous-product-cycle`. It is deliberately separate from
  the versioned runtime directory; the old runtime is preserved by a rename.
- An archive member cannot be a symlink, device, pipe, traversal path or
  duplicate. The source cannot include symlinks in any path component.
- SQLite is copied using SQLite's online backup API and integrity-checked.
  Private files are archived with per-file SHA-256 hashes and checked for
  changes during reading; the archive and database have separate hashes.
- Snapshotting happens only while both the VPS cron cycle lock and the direct
  Python production-cycle lock are held and the factory cron marker is paused.
- An existing checkpoint is never overwritten. Insufficient free disk,
  unreadable/oversized source, changed files and failed verification block the
  deployment, without treating it as a successful private cycle.

## Deployment transaction

1. Perform read-only global one-product preflight, owner/receiver trust checks
   and privileged scheduler inventory.
2. Stage an entire new runtime in a separate directory, including the full
   nested product tree. Run syntax checks before touching the active version.
3. Pause only the marked factory cron line while holding the lock. Capture
   private data with `factory_private_checkpoint_v1.py snapshot` and
   independently run its `verify` command.
4. Rename the previous runtime into a recoverable timestamped backup directory
   and rename the fully staged runtime to the canonical path.
5. Run the first private cycle and verify that the publication gate is still
   locked. Only then install the new cron line.

## Two different failure paths

**Before the first new cycle starts:** restore the prior runtime and original
cron entry, retaining the isolated checkpoint and any rejected runtime for
diagnosis.

**After the new cycle starts:** never automatically replace the private database
or replay the former cron against potentially advanced state. Quarantine the
factory by pausing its cron entry. Preserve both runtime versions, the complete
checkpoint, and the current private state for expert reconciliation.

## Recovery is not yet independently proven

The local checkpoint manifest explicitly records
`independent_offhost_copy_verified: false` and
`auto_restore_authorized: false`. Matching local SHA-256 digests are integrity
checks **not signatures**, offsite recovery, proof of genuine owner approval,
or evidence that the entire VPS is restorable. The snapshot is not a
transactional image of unrelated writers that ignore factory locks.

No process is authorized to auto-restore mutable state from this checkpoint.
Any later recovery needs a verified copy stored independently from the VPS,
an offline restore rehearsal in a separate path, an authenticated owner
decision and proof that post-checkpoint legitimate orders will not be lost.

## Independent-host attestation protocol (prepared, not executed)

The new `factory_offhost_restore_attestation_v1.py` has two strict modes:

1. On a separately controlled recovery host, transfer the three checkpoint
   files with a trusted private transfer mechanism. Run the local checkpoint
   verifier and then `rehearse --checkpoint ... --host-id ... --receipt ...`.
   It reconstructs every private file in an isolated temporary directory,
   verifies the extracted hashes, copies and opens SQLite, and writes an
   unsigned receipt. The receipt MUST NOT be considered authenticated yet.
2. The independent host administrator signs those exact receipt bytes using a
   private key that is NEVER installed on the factory VPS or stored in GitHub.
   For RSA/ECDSA keys, the signing primitive is:

   `openssl dgst -sha256 -sign RECOVERY_PRIVATE_KEY.pem -out receipt.sig receipt.json`

3. On the factory VPS, `verify --checkpoint ... --receipt ... --signature ...
   --public-key ... --expected-host-id ...` checks the exact signed bytes,
   root-owned protected public key, host identity, freshness, restored counts,
   and all local checkpoint hashes. It does not accept unsigned, stale,
   self-asserted or wrong-checkpoint receipts.

The first real signed receipt can only be obtained after the owner selects and
authorizes an actually independent storage host and its administrator
provisions the separate signing key. No such remote destination or trusted
receipt has been demonstrated in this draft. The activation workflow remains
**HOLD**; the independent-host protocol is not wired to automatic publication.
The workflow's initial source guard now exits with
`F01_OFFHOST_SIGNED_RECOVERY_NOT_YET_INTEGRATED_HOLD` **before SSH or any
live mutations**. Removing that guard requires a separately reviewed
two-phase off-host copy, signed receipt validation and explicit owner
authorization; an unsigned or locally self-attested JSON flag is not enough.

This proposal does not change existing factory status: **HOLD / NO GO**.
