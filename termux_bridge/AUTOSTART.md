# Termux autostart for Saeit safe command bridge

The phone-side Git SSH command channel is **verified**: an Android Termux
instance returned `pong` and `whoami_check_passed` to this isolated
branch in commits
[9b2c96f](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/9b2c96f0d22d98e4af7e7da798c5b0bf7150029b)
and
[eda3f74](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/eda3f7419494df5994eca94c4cb8bf49ca75a256).
Those are real Termux receipts. The GitHub Issues PAT workaround is no
longer needed; it is not used by this boot service.

**One-time local activation:** stop the prior foreground
`python -m termux_bridge.worker --loop --interval 300` with Ctrl+C,
then inside the existing dedicated checkout run:

```bash
git pull --ff-only && python -m termux_bridge.autostart --setup
```

This installs a private Termux:Boot hook at
`~/.termux/boot/50-saeit-termux-bridge` and launches the dedicated
background worker. Installation is idempotent. It does not overwrite
unrecognized boot hooks or modify any other phone folders.

For autostart after **phone reboot**, install **Termux:Boot** from the same
trusted distribution as Termux, open the Termux:Boot app once to enable
its boot receiver, and adjust Android battery/background restrictions
for Termux and Termux:Boot if needed. These Android app and OS settings
cannot be applied merely by GitHub; an existing app installation has
not been independently confirmed. If setup says
`TERMUX_BOOT_APP_NOT_CONFIRMED`, background start may still work now
but boot-after-restart is **not assured**.

Use `python -m termux_bridge.autostart --status` from the checkout
to check status without changing anything.

The launcher uses a Python file lock to prevent two managed background
instances. It polls every 300 seconds and runs only fixed allowlisted
`ping`, `whoami_check`, and `python_check` actions. No arbitrary
shell actions, systemd services, public ports, factory changes or
secret publication are implemented.

Android may pause or kill background processes unless background
execution is permitted. GitHub CI verifies Python logic and file
safety, but **not** Android reboot/battery behavior.

## ComfyUI phone SSH preparation (15 October 2026)

The live Git bridge returned an actual `pong`. A **new**, allowlisted
`comfyui_key_prepare` action is implemented and CI tested. It creates (or
reuses) `~/.saeit-comfyui-phone/comfyui_ed25519` and reports only the matching
`ssh-ed25519` **public** key in `bridge/result.json`. No commands or private
keys are obtained from GitHub, and the operation does not open a socket.

IMPORTANT: the existing Android Python worker cannot hot-reload updated Python
functions merely because its dedicated checkout did `git pull`. Once, on the
phone in Termux, restart the already running worker using:

```bash
pkill -f '[t]ermux_bridge.autostart --run' 2>/dev/null || true
pkill -f '[t]ermux_bridge.worker --loop' 2>/dev/null || true
cd "$HOME/.saeit-termux-bridge/repo" && git pull --ff-only &&
python -m termux_bridge.autostart --start
```

The issued Git command `comfyui-key-prepare-20261015-0956` expires at
2026-10-16 09:56:47 UTC. If it has expired, the owner must send a new command.
A matching receipt, **not** a passing CI test, is proof that this new action
ran on the physical phone. A privileged workflow on `main` independently
validates a completed phone receipt from the exact tested Git commit before it
adds a strictly forwarding-only public key to the existing VPS. The private key
must never be submitted, logged, or committed. Phone SSH tunnel activation and
browser availability remain separate checks.

