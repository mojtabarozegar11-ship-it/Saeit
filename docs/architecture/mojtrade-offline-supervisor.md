# MojTrade — GitHub-Independent Offline Evidence Supervisor

**Safety boundary:** this is a local, read-only research-evidence observer plus
private state-transition journal. It is **not** a broker bot, a production
signal publisher, a DEMO order simulator, or a release-approval mechanism.
It cannot issue orders or public signals, even if all its inputs are present.

## What this implements

- A self-contained Python 3.11 CLI with **no runtime imports, subprocesses,
  credentials, URLs, relay or network calls to GitHub**. Once source files and
  datasets are supplied locally, ordinary invocations and optional watch mode
  can run without GitHub Actions or an internet connection.
- Strict, absolute local-path config; private `0600` config; operator-owned
  regular files with non-writable group/other permissions; operator-owned
  `0700` private state directory. Symlinked/non-regular files and oversized
  inputs fail closed.
- Re-checks a frozen Strategy Foundry report, exact training dataset,
  separately dated OOS dataset, *already-existing* locked independent OOS
  journal, and the dependency-sensitive OOS research diagnostics. It **never
  creates or revises** the original independent OOS experiment.
- A `STOP` entry (even a suspicious/broken symlink) in the private state
  directory results in `OPERATOR_STOPPED`; watch mode exits without another
  iteration. Removing the operator stop entry permits a new offline scan.
- A private `0600` hash-chained, lock-protected state-transition journal.
  **Identical polls are not counted as new actions or reports.** Status flips,
  tampered data, stop/resume or changed evidence create one unique transition.
- A single-instance exclusive advisory lock (`supervisor.lock`, mode `0600`):
  a second local monitor is rejected, including simultaneous one-shot and
  watch invocations. The lock is released when the process exits, without
  deleting the reusable lock file.
- An **independent atomic liveness heartbeat** (`health.json`, mode `0600`)
  updated on each successful inspection. It does **not** create a duplicate
  material state transition. A read-only status command classifies a missing,
  altered, stale or future-dated heartbeat as blocked/stale and never assumes
  that a fresh timestamp conclusively proves the process is still running.
- On error, output is `BLOCKED_EVIDENCE`; with complete but unauthenticated
  local data, output is `RESEARCH_EVIDENCE_OBSERVED_UNVERIFIED`. There is **no
  READY_TO_TRADE state** in this implementation.
- Hard-coded `real_orders=0`, `public_signals=0`, `commercial_ready=false`,
  `broker_eligible=false`, and `publish_eligible=false` in every result.

## Local configuration

Create the operator-owned working/state directory with mode `0700` and use a
**private, mode `0600`** configuration file containing only these five keys:

```json
{
  "schema": "mojtrade.offline-supervisor.v1",
  "foundry_report": "/private/absolute/path/foundry.json",
  "training_data": "/private/absolute/path/training.json",
  "unseen_data": "/private/absolute/path/unseen.json",
  "private_oos_ledger": "/private/absolute/path/frozen-oos.jsonl"
}
```

The OOS ledger and its parent directory must have previously been created by
the one-shot independent validation flow, in `0600` and `0700` modes
respectively. **Do not insert broker keys, API tokens, exchange passwords or
wallet secrets into any config or dataset.**

One offline inspection:

```bash
python3 scripts/mojtrade_offline_supervisor.py \
  --config /private/absolute/path/supervisor.json \
  --state-dir /private/absolute/path/operator-state
```

Long-running local status observer (purely offline, no external actions):

```bash
python3 scripts/mojtrade_offline_supervisor.py \
  --config /private/absolute/path/supervisor.json \
  --state-dir /private/absolute/path/operator-state \
  --watch --interval-seconds 60
```

Read only the latest heartbeat and its age, with the default stale threshold
of three observation intervals (180 seconds for the default 60-second cycle):

```bash
python3 scripts/mojtrade_offline_supervisor.py \
  --status --state-dir /private/absolute/path/operator-state \
  --interval-seconds 60
```

The status command needs no broker credential, GitHub connection or even the
original market-data config. It does not modify the event journal or heartbeat.
Possible states are `MISSING_OR_CORRUPT_HEARTBEAT`, `CLOCK_SKEW_BLOCKED`,
`STALE_HEARTBEAT`, `OPERATOR_STOPPED`, and
`RECENT_HEARTBEAT_NOT_PROOF_RUNNING`. **None** enables trading or publishing.

Create `operator-state/STOP` to halt the watch loop; remove only that explicit
operator stop entry to resume a **research-status** observer. A stop is never
an order cancellation or a broker kill switch because this service has no
broker connection whatsoever.

The `state-changes.jsonl` file records only **new material** state transitions
with timestamps, SHA-256 chained entries and exclusive advisory locks. It is
bounded to 500 entries / 5 MB and refuses further writes when full. SHA-256
chains detect accidental/local modification against a retained checkpoint;
they are *not* externally signed tamper-proof evidence. To continue beyond the
capacity safely, an operator must archive and deliberately provision a new
private journal; the code never rotates or destroys evidence automatically.

## Packaging for eventual VPS operation — NOT DEPLOYED

Once the Python files and their dependencies are copied to an owner-approved
VPS destination, a standard service manager *could* supervise the observer
without GitHub Actions. An example template, **not installed or activated**:

```ini
[Unit]
Description=MojTrade offline research evidence supervisor (no trading)
After=local-fs.target

[Service]
Type=simple
User=REPLACE_WITH_DEDICATED_UNPRIVILEGED_USER
WorkingDirectory=/REPLACE/WITH/LOCAL/PROJECT
ExecStart=/usr/bin/python3 /REPLACE/WITH/LOCAL/PROJECT/scripts/mojtrade_offline_supervisor.py --config /REPLACE/PRIVATE/supervisor.json --state-dir /REPLACE/PRIVATE/operator-state --watch --interval-seconds 60
Restart=on-failure
RestartSec=10
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

This is **not** permission to merge, deploy, restart the VPS, connect trading
accounts, publish signals, pay for services, or touch production data.
Production ownership, local paths, access controls and service confinement
must be independently reviewed before any installation.

## Current evidence limits

All regression fixtures are synthetic. Neither a file checksum nor a
successful process/CI proves real market-data origin, available-at timing,
broker execution quality, profitable strategies, or independent statistical
significance. A genuine forward, read-only/DEMO evidence program is still
required before considering a separate live-trading project.

Run local regressions with:

`python3 -m unittest -q tests/test_mojtrade_offline_supervisor.py`
