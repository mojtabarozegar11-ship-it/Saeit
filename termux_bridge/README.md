# Saeit / Termux safe GitHub command bridge (isolated prototype)

Scope: only repository mojtabarozegar11-ship-it/Saeit, branch feature/termux-safe-command-bridge-20261014 and a dedicated clone under ~/.saeit-termux-bridge/repo on Android. No deployment to cPanel, VPS, the factory, or other repositories.

## Files

- bridge/command.json: short-lived request with one exact action name.
- bridge/result.json: sanitized execution receipt (never raw output).
- bridge/status.json: protocol state without device identity.
- termux_bridge/worker.py: stdlib-only Git pull / allowlisted execution / Git push worker.
- tests/test_termux_bridge.py: unit and temporary local-Git integration tests.

## Fixed, safe operations

| Action | Local operation | Public receipt |
|---|---|---|
| ping | protocol response | pong |
| whoami_check | id -un (without a shell) | whoami_check_passed/failed; no username |
| python_check | Python availability check | python_available |

Unknown keys, arbitrary command strings, expired or too-far-future requests and non-allowlisted actions are refused. A recently acknowledged command ID will not execute a second time. Git SSH uses existing credentials on the phone with strict known-host checking. No token, key or stdout is published.

The repo is PUBLIC. Never publish passwords, SSH private keys, usernames, IPs of the phone, contacts, identifiers or private content in these command files, results, issue bodies, commits or CI logs.

## Critical activation limitation

Tests run on a GitHub-hosted Ubuntu runner, NOT on an Android phone. The most recent real VPS-to-Termux test failed with TERMUX_BRIDGE_METADATA_MISSING and a separate read-only audit found port 18022 not listening. There is no verified phone-side agent running at present. Merely merging or testing this bridge cannot turn on Termux or run a phone command.

When and only when a trusted service already has access to the phone, it can use the pre-existing phone-local Git SSH credentials to clone the dedicated branch and run python termux_bridge/worker.py --once, or run python termux_bridge/worker.py --loop --interval 120. The latter polls GitHub without consuming ChatGPT tokens. This project does not grant phone permissions or start a background service by itself.

A production rollout still needs phone-side installation, confirmation of Git push authorization, host key pinning, battery/background handling and safe authorization of command writers.

## Local testing

Run: python -m unittest discover -s tests -p test_termux_bridge.py -v

The tests create a temporary bare Git repo and validate request handling, safe execution, sanitized result push and duplicate suppression. They require no network service, smartphone or VPS.
