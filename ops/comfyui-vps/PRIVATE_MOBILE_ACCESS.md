# Secure mobile ComfyUI access — onboarding

The existing CPU-only ComfyUI installation was verified running locally at `127.0.0.1:18188`. **Never publish this local port, and never use Tailscale Funnel.**

The VPS has no sudo for `githubops`; the officially sourced static Tailscale 1.104.1 binaries were staged at `/home/githubops/.local/opt/comfyui-tailnet/binaries-1.104.1`. Userspace daemon smoke test succeeded without privileges, and the smoke daemon was stopped after testing.

## Required one-time account action

You must authorize a tailnet controlled by you. No installer can safely complete a private enrollment without your authorization.

1. Sign in to your own Tailscale account at https://login.tailscale.com/admin/settings/keys (create one if necessary). Generate a **short-lived, one-time (non-reusable)** auth key that is permitted to enroll this one VPS, with minimum possible permissions. Do **not** share it in ChatGPT.
2. In the **Saeit** repository's **Settings > Secrets and variables > Actions**, create a repository secret named exactly `COMFYUI_TAILSCALE_AUTHKEY` with the key. Avoid public repo variables or commit files.
3. In GitHub Actions open **ComfyUI Tailnet Private Mobile Access**, click **Run workflow**, select `connect`. The controller passes the key using a private SSH transfer and the Tailscale CLI `file:` authorization format; it deletes the temporary VPS key file. It will print no auth token.
4. When connected, Tailscale Serve is configured for **tailnet-only** HTTPS proxying to `http://127.0.0.1:18188`. If the tailnet's HTTPS certificates are disabled, an administrator must enable this once in the Tailscale console; re-run `connect` afterward.
5. Install the official Tailscale Android app from Google Play (no Termux, Boot or F-Droid), log in **with the same tailnet account** and connect. Tailscale's machine list / Serve settings show the private `.ts.net` URL. Do not use Funnel.
6. To see the actual ComfyUI canvas, start a bounded ComfyUI session from GitHub Actions **ComfyUI VPS Private Lifecycle Control** (`start`, 5–60 minutes), then browse the tailnet-only HTTPS address. It will become unavailable when ComfyUI stops; this prevents ongoing CPU use.

## Verified and remaining

- [x] GitHub Actions SSH fingerprint and key tested to the VPS.
- [x] Existing isolated ComfyUI CPU runtime started and returned HTTP 200 in a bounded session.
- [x] Current VPS audited (no sudo, no Tailscale package).
- [x] Rootless Tailscale static binaries staged.
- [x] Userspace Tailscale daemon smoke successfully starts/stops.
- [x] Tailnet private gateway script added and `status` tested (stays off by default).
- [ ] Your `COMFYUI_TAILSCALE_AUTHKEY` secret is not configured; VPS node has **not** joined any tailnet.
- [ ] Tailnet HTTPS Serve endpoint not yet configured or reachable from mobile (requires enrollment).
- [ ] Auto-resume after VPS reboot not configured; rootless startup mechanism must be assessed separately.

## Security

- Userspace daemon is scoped to `githubops` with private state directory and no system service.
- Never modify or restart `~/factory-runtime`.
- Only permit owner-controlled devices in tailnet access policies; private tailnet != per-user access control if others share the network.
- Tailnet HTTPS is **not an Internet-public tunnel**; do not open inbound VPS firewall ports.
- This repository may be public. Do not write auth URLs, credentials, model prompts, private files, or tailnet hostnames in logs.
- Tailscale credentials never belong in a Git commit. If leaked, revoke and replace them immediately.
- To disconnect the overlay safely, choose `disconnect` in GitHub Actions; this does not stop any factory process.

Official references:
- https://tailscale.com/docs/concepts/userspace-networking
- https://tailscale.com/docs/reference/tailscale-cli/serve
- https://tailscale.com/docs/features/access-control/auth-keys
