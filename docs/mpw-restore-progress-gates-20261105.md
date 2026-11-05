# MojPlayWin encrypted-backup isolated restore: timeout diagnostic

Current evidence (workflow run 41444903762, 2026-11-02): manifest-only
pair readiness passed, but the private SQL -> isolated MariaDB pipeline reached
the 5,500-second limit with source and consumer exit code 124. No completed
GPG stream integrity check or successful isolated SQL restore was recorded.
No release or backup recoverability claim follows from that run.

The owner-armed workflow now relays SQL through
`scripts/mpw_isolated_sql_progress_20261105.py` *between* the same pinned VPS
source and a network-disabled temporary MariaDB Docker container. The relay
copies the binary stream unchanged and emits only integer GiB milestones to
stderr; it never parses, saves or logs SQL rows, table names, credentials,
emails, paths or hashes. Its 48 GiB upper bound matches the source producer.

The workflow checks all three pipeline exit codes, classifies exit 124 as
`ISOLATED_IMPORT_TIMEOUT`, and still requires independent source GPG/SHA256
validation, a successful MariaDB import, nonempty restored schema/tables and
the subsequent private file-root restore. A relay EOF is **not** proof of any
of these requirements.

This commit changes GitHub source only. `workflow_dispatch` remains protected
by the existing owner/branch/confirmation gate; no action is scheduled by this
change, no backup is created, and no cPanel or live payment code is changed.
Another long restore is not justified solely to collect milestones: first
review encrypted manifest size, runner/VPS resource budgets, and an approved
restoration plan. The owner must separately approve the next expensive run.

## Evidence-based capacity gate (2026-11-05)

Earlier owner-armed runs recorded an immutable SQL pair with 17,901,542,305
plaintext bytes (~16.67 GiB) and 2,323,314,600 encrypted bytes (~2.16 GiB).
The scoped files archive held 533,944,368 plaintext bytes (~0.50 GiB).
GPG roundtrip/source metadata verification **does not** prove importability.
The failed isolated SQL restore (run 41444903762) timed out after 5,500 s.

The existing GitHub runner admission guard used only 9 GB of free space,
which is smaller than even the logical SQL plaintext. The new `estimate-pair`
mode checks the exact two private set manifests and calculates a coarse GiB
screening threshold: max(9 GiB, 2 x SQL plaintext + 6 GiB, 2 x scoped files
plaintext + 6 GiB), rounded upwards. This example implies a **40 GiB free
space floor**. The owner-armed workflow refuses to pull Docker or decrypt SQL
on a runner beneath that threshold. No actual GitHub runner capacity is
asserted; MariaDB table/index/temp growth could exceed this reservation.

This gate reads validated private manifests only; it performs no GPG decrypt,
SQL import, remote mutation, customer data disclosure or owner-triggered run.
Passing it neither proves source integrity nor permits a site release.

## VPS feasibility must be measured separately (cycle 49)

Official GitHub `ubuntu-latest` standard runners provide only 14 GB SSD,
irrespective of whether the repository is public or private. This is below
the 40 GiB admission floor for the observed logical SQL dump. Repeated
attempts to import this pair on that standard runner are not justified.

A previous read-only inventory (2026-10-29, workflow 40802377602) reported
zero free VPS bytes, no Docker/MariaDB executable, and about 3.2 GiB available
memory **at that time**. Later, the 2026-11-02 encrypted backup preflight
(workflow 41417395178) proved only a 10 GiB free-space admission threshold;
this is not proof of the much larger restore requirement. Today's actual VPS
capacity and isolation toolchain remain unverified.

The read-only `inspect-vps-pair` mode checks the *specific pair* metadata,
free space at the intended account's home filesystem, a 4 GiB available
memory reserve and local Docker/native MariaDB executable presence. It never
launches Docker, initializes a DB, imports SQL, exposes records or modifies
any VPS/cPanel state. Executable presence is **not** operability proof.

The existing **MojPlayWin cPanel Passenger inventory (read only)** manual
workflow now accepts optional `restore_pair_id`. When supplied, it performs
this private read-only VPS preflight through the already pinned SSH transport.
No workflow is dispatched by these source-only changes. Even a positive
preflight would require an independently isolated runtime, resource safety
assessment against the single-product factory, and owner approval before any
costly restore. Never restore into the production cPanel database.


## Cycle 50 verified live read-only audit and cycle 51 bounded next step

The successful read-only inventory run
https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/41967282629
measured **7,102,246,912 free VPS bytes** (~6.61 GiB) and
**7,690,735,616 available memory bytes** (~7.16 GiB). The `githubops`
VPS command search found no accessible Docker/Podman or self-contained
MariaDB server and initialization executable. These facts establish a
**NO-GO** for a 40 GiB admission-screen restore on the observed home
filesystem. They do not establish that encrypted backup pair files are
missing: a separate legacy fixed-name metadata probe does not enumerate
the current immutable Nov 2 set.

The same run reported cPanel account quota
**32,212,254,720 bytes**, used **28,752,969,728 bytes**, leaving
**3,459,284,992 bytes** (~3.22 GiB) of account quota; its host-global
free-byte reading does not override that quota. cPanel is also the
production host and must not be treated as an isolated restore target.
The total reported sizes of three account databases were
**16,680,583,168 bytes**, not a confirmed map of which is the active
MojPlayWin database. No production DB contents were read in this audit.

Cycle 51 adds `scripts/mpw_vps_mount_capacity_readonly_20261105.py`:
a mountinfo/stat-only, privacy-preserving probe for *distinct* local
filesystems. It deduplicates bind mounts by device, ignores network and
virtual filesystems, prints no mount paths or device IDs, and cannot
write, mount, decrypt, restore or restart anything. Tests use synthetic
mount tables. The existing read-only workflow is prepared to execute
this script over the pinned VPS SSH relay, but the **feature-branch
changes have not been merged or run on the VPS**. Thus whether any
alternative independent mounted filesystem actually has enough
available capacity remains **unknown**. Even a candidate with enough
space is not automatically approved or safe for the single-product
factory. Independent permission, factory isolation, and DB runtime
readiness must be assessed before owner-approved restore.
