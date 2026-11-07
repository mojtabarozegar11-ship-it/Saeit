# MojTrade — independent VPS capture guard (NOT installed)

This package is a code-only **release safety boundary** around the existing
public, forward-hourly market-data collector. It does not install cron,
systemd, secrets, brokers or public signal publishing; it makes no trades.

## Read-only operator preflight

Run from an operator-controlled copy of the **matching scripts directory**:

```bash
python3 scripts/mojtrade_vps_capture_guard.py \
  --symbol BTC-USD \
  --venue coinbase-exchange-public-candles \
  --private-journal /absolute/private-owner-0700/btc-coinbase.jsonl
```

Use the exact provider label exported by the existing market observer; check
`--help` for supported values. `--check` is the default and does not fetch
market data, create files or start a service. Inspect the returned machine-
readable `LOCAL_READINESS_ONLY_NOT_ACTIVATED` or `BLOCKED` receipt.

Gates: absolute paths without symlink ancestry; owner-only 0700 journal
directory; existing owner-only 0600 single-hardlink journal; intact hash-linked
observation history; **one and only one** symbol and quote-capable venue;
all observations having same-venue public quote receipts; owner-controlled,
non-group-writable local source code; measured fingerprints for four required
scripts; **minimum 2 GiB plus 16 MiB free and at least 16 available inodes on
the journal filesystem**. A pre-existing capture lock must itself be a
single-hardlink, owner-only 0600 regular file; an unsafe lock blocks even
the read-only preflight. The check reports whether a private lock file exists,
but does **not** treat lock-file existence as proof a process is running.
Exclusive lock acquisition remains mandatory in the explicitly invoked run mode.

Fingerprints report local observed bytes; they do not prove a source archive was
deployed, the VPS was running, provider provenance, research success or live
profit. Check machine clock/NTP and filesystem mount independently.

## Prospective runtime mode (not activated)

Only after independent operational review, an operator may choose the explicit
one-shot `--run` option. It **never** uses a broker, order endpoint, wallet,
GitHub Actions, signal publishing API or email. It accepts only BTC-USD/ETH-USD
and one explicitly chosen venue **Coinbase Exchange or Kraken Spot**; no
automatic venue fallback is allowed. It refuses attempts outside UTC minutes
05–24 and reserves a private exclusive lock to prevent overlapping fetches.
After response, it rechecks local safety, then appends only a valid same-venue
quoted closed hourly bar to an owner-only hash-linked journal. Missing, stale,
crossed or unquoted data fail closed: no bar is recorded.

Actual forward data still require **at least 100 real consecutive hours**.
Missing hours can reset a research-eligibility streak. The separate forward
dataset gate additionally requires all receipt timestamps and quote evidence.
No data are backfilled as if observed earlier.

**No schedule has been installed**. Two independent, *review-only* systemd
unit templates are supplied at `deploy/systemd/mojtrade-forward-capture.service`
and `deploy/systemd/mojtrade-forward-capture.timer`. The timer is pinned to
`07` minutes past each UTC hour, with `Persistent=false`, no random delay and
one-second accuracy. A server outage or service failure therefore cannot
trigger an artificial catch-up run for missed observations. The service has a
read-only preflight, explicitly runs this guard with `--run`, uses a private
dedicated journal, disallows restarts and bounds a stuck fetch to 120 seconds.
Its systemd filesystem sandbox allows writes only inside the designated
private journal directory. Source writes and Python bytecode generation are
disabled. These templates **do not deploy, enable or start themselves**.

The template hard-codes *proposed* `githubops` paths and one Coinbase BTC-USD
venue; these paths are **not evidence that the actual VPS has matching files**.
Do not blindly install. Before any future activation, independently confirm
all four source SHA-256 values, 0700/0600 permissions, absolute path ownership,
mount-local free bytes/inodes, NTP/UTC clock, systemd version and sandbox
compatibility, provider connectivity, recovery/backup policy, and whether
legacy observer timers, cron, or the active GitHub relay could write or compete.
Inspect with `systemd-analyze verify` and `systemd-analyze calendar`, then use
the guard's read-only `--check`. The current VPS health/run evidence is not
equivalent to confirming the journal filesystem. A stopped/disabled timer does
not kill a currently running oneshot service: in a future approved cutover,
stop both the `.timer` and `.service`, verify no capture process remains, and
retain the private journal without deletion. No scheduled run counts as a
valid observation unless a fresh same-venue quote receipt is appended.

Time-zone handling, disk recovery, monitoring, backups and actual server
credentials remain release gates. The historical PR #1976 disk warning was
approximately 1.06 GiB free, although newer VPS root evidence has shown more
space; neither observation replaces checking the actual journal mount. This
script must not be invoked in `--run` mode on an unverified VPS.

No rollout, merge, GitHub Actions deployment, payment, real order, public
signal, restart or email is included. All tests are offline fixtures.

## Separate legacy private observer — not research capture

`deploy/install_mojtrade_observer_vps.sh` and the manual-only
`mojtrade-vps-observer-activate.yml` workflow serve a legacy private
hourly signal payload, **not** the same-venue, quote-backed research journal.
They now require at least 2 GiB + 16 MiB free and 16 available inodes on
both relevant VPS paths, with a strictly read-only pre-upload check before
the workflow creates directories or uploads any source. The installer
rechecks capacity before its local changes. None of this proves the legacy
observer is installed or safe to activate. Existing GitHub relay writes and
local scheduler collisions still require an independent cutover review;
legacy payloads must never be counted toward the 100-hour research dataset.

The manual legacy activation workflow also fails closed before SSH unless
the owner gives an explicit acknowledgement and GitHub's read-only Actions
API confirms the existing hourly relay is `disabled_manually` and no recent
relay run remains pending. This is a deployment-only check; it introduces
no GitHub runtime dependency for the future VPS process. The relay has
**not** been disabled in this PR. A separately approved cutover is required.
