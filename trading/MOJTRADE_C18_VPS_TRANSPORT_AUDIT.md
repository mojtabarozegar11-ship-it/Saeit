# MojTrade C18 — one-shot VPS SSH transport evidence

## Why this gate exists

The most recent inspected `mojtrade-readonly-relay.yml` run
`42470213402` failed with exit code 1, without a diagnostic message
identifying the first failed shell command. Source inspection alone cannot
establish whether the VPS SSH port, server identity or a later credentialled
step caused the failure.

The separate C18 PR-only workflow deliberately does **only** two read-only
network checks on the VPS endpoint already pinned by the existing relay:

1. Open a TCP connection to port 22 and read the SSH protocol banner.
2. Obtain the public RSA host key without authenticating and compare its
   SHA-256 fingerprint with the previously committed pinned fingerprint.

The C18 job is restricted to its exact same-repository PR branch. It uses no
SSH private key, password, cTrader account, bearer token or payment credential.
It never logs in, executes a remote shell, copies files, touches the database,
deploys the bot or places orders. A failure stays visible in this diagnostic
job while the C# compile and Python regression checks remain separate.

## Diagnostic outcomes and safe interpretation

| Marker | What it establishes | What it does not establish |
| --- | --- | --- |
| `MOJTRADE_C18_TCP_TIMEOUT` | TCP connection to SSH timed out from this runner | VPS is down for every other network path |
| `MOJTRADE_C18_TCP_REFUSED` | TCP connection was explicitly refused | Why the VPS/firewall refused it |
| `MOJTRADE_C18_TCP_ERROR` | Another TCP socket error blocked connection | A specific server-side cause |
| `MOJTRADE_C18_SSH_BANNER_TIMEOUT` | TCP connected but the SSH banner timed out | Server or network root cause |
| `MOJTRADE_C18_SSH_BANNER_ERROR` | TCP connected but reading the banner failed | Server or network root cause |
| `MOJTRADE_C18_UNEXPECTED_SSH_BANNER` | Port response is not the expected SSH v2 banner | Any specific attack or server fault |
| `MOJTRADE_C18_RSA_HOST_KEY_UNAVAILABLE` | The earlier pinned RSA key could not be retrieved | Why the port/key service behaved differently |
| `MOJTRADE_C18_HOST_KEY_MISMATCH_STOP` | The observed RSA fingerprint differs from the pinned source value | That the changed host should be trusted |
| `MOJTRADE_C18_PINNED_RSA_HOST_KEY_MATCH` | TCP/SSH reachability and public host identity match from the runner | SSH authorization, service installation, TLS, cTrader, database, trading or commercial readiness |

The pin must **never** be overwritten automatically. If it changes, verify
the host identity through an independent owner-controlled channel before
any credential-bearing operation.

## Remaining gates

Even a successful probe does not supply the VPS's actual Python/systemd
state, disk/backup/restore evidence, private TLS health, or authenticated
cTrader DEMO positions/orders/deals. Those require separately authorized,
read-only runtime inspection. Until then, all trading and public signal
publication remain disabled; this PR remains Draft, with no merge or deploy.
