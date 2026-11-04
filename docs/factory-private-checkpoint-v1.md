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

This proposal does not change existing factory status: **HOLD / NO GO**.
