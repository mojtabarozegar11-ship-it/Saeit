# MojTrade C09 — build and VPS installation gates

**Not installed; not approved for runtime trading.** This package does not
contain a compiled `.algo` and has not been deployed to a VPS.

## Build

1. A supported machine must have the .NET 8 SDK and NuGet access to the
   official `cTrader.Automate` package. Each cBot is a **separate** class
   library targeting `net8.0`, pinned to package version `1.0.21`.
2. Run `bash scripts/mojtrade_build_cbots.sh`. It terminates nonzero if
   `dotnet` is missing or older than version 8. This is **not a success
   indicator** until each project compiles and the resulting `.algo` exists.
3. Verify the `.algo` metadata in the supported cTrader desktop/CLI, confirm
   two independently named robots and expected parameters, and sign the build
   hashes against their exact Git commit. Do not copy unsigned artifacts.

Official documentation:
- https://help.ctrader.com/ctrader-algo/documentation/visual-studio-ides/
- https://help.ctrader.com/ctrader-cli/setup/
- https://help.ctrader.com/ctrader-cli/cbots/

## Central service — dormant installation plan (not executed)

1. Deploy reviewed Python source to `/opt/mojtrade` on the owner-approved VPS.
2. Create an unprivileged `mojtrade-risk` account and private writable
   `/var/lib/mojtrade-risk` directory. A dedicated protected environment file
   must be placed at `/etc/mojtrade-risk/risk.env` with file permission 0600.
3. Generate a fresh 32+ character random secret **on the VPS**; never put it in
   GitHub, chat, email, logs or a browser query. The tracked example value
   `CHANGE_ME` is deliberately too short to start the service.
4. Review `deploy/mojtrade-risk.service`; it binds to loopback only,
   applies filesystem hardening and omits
   `--enable-demo-reservations`. Copying/installing it does **not**
   authorize activation of trading.
5. Put an HTTPS reverse proxy, access control and rate limiting in front of the
   loopback service before client connection. Allow only the intended source
   IPs. No public raw port 8765.
6. Enroll the correct **demo** account number, UTC-day starting equity and
   review its actual broker positions. Without a valid baseline, reservations
   are denied. Confirm server and broker clocks, alerting and recoverability.
7. Keep both cBots' `EnableCoordinatedDemoTrading` false until C# compile,
   startup, fault-path checks and separate owner approval. Never enable
   real-account trading through this project.

## Evidence collected in C09

- Local environment: `dotnet` **not installed**; `ctrader-cli` **not installed**.
- Build wrapper correctly stopped with exit code 2 and no cBot artifact.
- `systemd-analyze verify deploy/mojtrade-risk.service` completed successfully.
- Python static/contract/ledger tests passed. These cannot replace cTrader
  compilation, broker reconciliation or independent VPS deployment verification.

Release remains blocked until a trusted cTrader build environment and an
approved VPS connection are actually available. GitHub Actions may retain code
but must not be the permanent service runtime.
