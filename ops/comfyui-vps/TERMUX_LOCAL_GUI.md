# ComfyUI graphic canvas on Android without Tailscale

**Architecture:** Android browser -> `http://127.0.0.1:18189` (Termux loopback) -> SSH encrypted local forward -> VPS `127.0.0.1:18188` (ComfyUI CPU isolated). The VPS ComfyUI port must NEVER be exposed on `0.0.0.0`.

This is a **phone-local SSH tunnel**, not a public site or a reverse tunnel. The old Termux GitHub `pong` bridge is not sufficient for SSH authorization; the pre-existing VPS reverse SSH check failed with `TERMUX_BRIDGE_METADATA_MISSING`. These instructions authorize a separate dedicated key with only permission to forward TCP to ComfyUI's loopback port. No Tailscale account, sudo, cPanel access, factory restart or VPS firewall opening is needed.

## One-time mobile setup

1. From the Android **Termux** shell, install the OpenSSH client if missing: `pkg install openssh curl`.
2. Fetch the reviewed helper (or copy it from this repo), **never provide any private key to GitHub/ChatGPT**:

   ```bash
   curl -fL https://raw.githubusercontent.com/mojtabarozegar11-ship-it/Saeit/main/ops/comfyui-vps/termux-local-gui.sh -o "$HOME/comfyui-local-gui.sh"
   bash "$HOME/comfyui-local-gui.sh" prepare
   ```

   `prepare` creates a new SSH key dedicated to this local GUI tunnel in `~/.saeit-comfyui-phone/`, if absent. It prints only the **public** `ssh-ed25519 ...` line. A key without a passphrase is used for easy manual forwarding, so protect your phone and revoke the VPS authorization if lost.

3. Copy **only that public key line**. Go to [ComfyUI Phone SSH Key - Private Local Canvas](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/workflows/comfyui-termux-local-ssh-key.yml) -> Run workflow -> `mode: authorize`; paste the public key into `public_key` and run. The GitHub Action connects over the *already-existing, host-pinned* GitHub Actions -> VPS SSH channel. It installs one SSH authorized key limited to `127.0.0.1:18188`, forced command `/bin/false`, with no interactive terminal, agent or X11 forwarding. The user's unrelated keys are preserved.

## Each session

1. Run [ComfyUI VPS Private Lifecycle Control](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/workflows/comfyui-vps-control.yml) with `action=start` for `15`, `30` or `60` minutes. Its controller will automatically stop ComfyUI at the session TTL. Make sure the action succeeds.
2. In Termux:

   ```bash
   bash "$HOME/comfyui-local-gui.sh" connect
   ```

   Leave that Termux session running. In the **same phone** browser, open `http://127.0.0.1:18189`. You should see the normal ComfyUI graphic canvas. Optional: in a second Termux tab, `bash "$HOME/comfyui-local-gui.sh" health`.
3. Stop the tunnel with Ctrl+C in Termux. You can stop ComfyUI via the VPS Lifecycle Control workflow `action=stop`.

The Android network must be able to reach the VPS SSH service over TCP/22; key authorization and the VPS `sshd` configuration must allow forwarding. If the VPS SSH service is unreachable or forbids forwarding, no GUI link can be claimed until that is fixed. The phone can suspend a Termux foreground tunnel when Android kills its process, so keep the session active.

## Revocation / security

- To disable phone access, run **ComfyUI Phone SSH Key - Private Local Canvas** with `mode=revoke`, which removes *only* the marked ComfyUI mobile key from `~/.ssh/authorized_keys`.
- `mode=status` checks only whether this dedicated key is present.
- The GitHub repository is public: never place SSH private keys, recovery codes, wallets, passwords, or authorization tokens in the repo, workflow inputs, or issue comments.
- ComfyUI's existing CPU/tiny-model experiment does **not** constitute a production 8K image generation system. The access tunnel changes connectivity, not model quality.
- Nothing here establishes a background service after Android phone reboot: this specific local tunnel runs while the Termux SSH client stays active.
