# ComfyUI on VPS — existing CPU runtime, no Termux dependency

Verified on 2026-10-14 using the established Saeit SSH relay (GitHub Actions -> githubops on VPS).

## Verified host facts
- VPS: 3 logical CPU, 3.8 GiB RAM, 27 GiB free disk (at verification)
- Existing installation: /home/githubops/comfyui-isolated (owned by githubops, private mode 0700)
- Existing source: source-v0.40.0; existing Python: env-cpu/bin/python (3.11.17)
- Existing PyTorch: 2.11.0+cpu, frontend package 1.55.17
- NVIDIA GPU was **not detected**. Large diffusion/video generation is not a realistic guarantee on this host.
- ComfyUI started with `--cpu --listen 127.0.0.1 --port 18188 --disable-auto-launch` and returned HTTP 200 from /system_stats.
- GitHub Actions start/stop smoke succeeded. The factory directory was not modified by this operation.

## Phone-based administration with GitHub (private actions, no open web port)

After the PR is merged to main:
1. Sign into the repository in GitHub using a write-authorized account.
2. Open **Actions** > **ComfyUI VPS Private Lifecycle Control** > **Run workflow**.
3. Select `status`, `start`, `stop`, or `health`. For start, select 5/10/15/30/60 minutes.
4. View the run log for the corresponding status; no Termux or Termux:Boot is necessary.

Only authenticated GitHub collaborators with workflow execution rights can run these actions. The repository's workflow configuration and logs may be public, so never put credentials, model inputs or private prompts in run parameters or logs.

**This is a private operation-control interface from a phone, not yet a browser-accessible ComfyUI canvas.** The ComfyUI HTTP interface remains bound only to loopback. For graphical remote access, set up a separate authenticated HTTPS gateway (e.g. restricted zero-trust tunnel) only after verifying authorization and domain access. Do not forward port 18188 to the public Internet.

## Implementation
- `.github/workflows/comfyui-vps-preflight.yml`: read-only VPS inventory via pinned SSH host fingerprint and existing `VPS_SSH_PRIVATE_KEY`.
- `.github/workflows/comfyui-vps-smoke.yml`: bounded CPU start-and-stop diagnostic.
- `.github/workflows/comfyui-vps-control.yml`: manual on-demand remote commands.
- `ops/comfyui-vps/control.sh`: restricted lifecycle manager, run over SSH as githubops, no sudo.
- ComfyUI starts only when explicitly requested; a `timeout` limits any session to the selected maximum, even if the phone is off.
- `stop` targets only the tracked process belonging to the existing ComfyUI Python environment.
- Logs and PID stored at `/home/githubops/comfyui-isolated/.control` (private).
- No cPanel, production website, factory database, Termux or unrelated repositories are modified.
- The previous duplicate root-level installer and system-wide unit have been deleted from this branch. Do not reinstall ComfyUI.

## Safety boundaries
- Requires the verified SSH fingerprint `SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs`.
- SSH key is never printed.
- No production factory process is stopped or restarted.
- No public listener; do not advertise a ComfyUI URL until an authenticated private gateway has been tested.
- CPU-only generation may be slow; only small test workflows should be attempted until memory and speed are measured.


## Oct 15, 2026: audited lightweight model, deployment QA

A reproducible candidate was installed and independently checked using GitHub Actions:
- Source: `turingevo/tiny-sd-safetensors`, `segmind_tiny-sd.safetensors`, derived from `segmind/tiny-sd`.
- Local candidate: `~/comfyui-isolated/source-v0.40.0/models/checkpoints/segmind_tiny_sd_candidate.safetensors`.
- SHA-256: `92e00b860c409f8cfc521a94f779009c6ebd28bf07670bf50e747682ab7b3b72`.
- 802 safetensors keys (358 UNet, 196 text encoder, 248 VAE), header verified without tensor loading.
- Real `/object_info/CheckpointLoaderSimple` and `/system_stats` returned HTTP 200 and the checkpoint was listed.
- Factory loop remained alive before/after model installation; no factory files were edited.
- Source model's usage restrictions should be checked against the original `segmind/tiny-sd` CreativeML OpenRAIL-M license. Do not rely on the mirror's Apache license tag as superseding upstream terms.
- The trial model is intended to prove functionality, **not** professional-quality or 8K production. The VPS has 3 logical CPUs and 3.8 GiB RAM with no verified NVIDIA GPU.

New isolated actions:
- `ComfyUI Model Readiness Audit` only reads the VPS, verifies model structure, current SHA-256 and factory presence.
- `ComfyUI Install Verified Tiny CPU Model` downloads one pinned-hash model on demand, with RAM/disk and factory-liveness preflight and atomic final placement.
- `ComfyUI Private Model API Integration` temporarily starts local ComfyUI, verifies the installed model is recognized, then stops.
- `ComfyUI CPU Image Production Proof` is a *low-resolution demonstration*, max 3 sampler steps, with a separate process, reduced CPU scheduling priority, soft data memory cap and RAM watchdog; on success uploads a single benign image as a GitHub Actions artifact. Never treat this smoke test as a high-quality production render.

No generated images, user prompts, or private credentials should be committed to this public repository. The actual graphical ComfyUI UI remains local-only; a private authenticated tailnet authorization is still required to browse it remotely.
