# ComfyUI on the existing VPS — verified operating status

**Scope:** only the existing `Saeit` repository and private `githubops` ComfyUI environment. Production factory, cPanel sites, Termux, unrelated repos and public networking were not changed.

## Proven end-to-end achievements (2026-10-15)

- VPS virtual CPU: 3 logical cores, QEMU x86-64, **SSE2 only**, without SSSE3/SSE4/AVX/AVX2/FMA/F16C/BMI2.
- ComfyUI remains an independent localhost-only, manually started CPU installation under `~/comfyui-isolated/source-v0.40.0`.
- Hash-pinned Tiny-SD technical test checkpoint: `segmind_tiny_sd_candidate.safetensors`, SHA-256 `92e00b860c409f8cfc521a94f779009c6ebd28bf07670bf50e747682ab7b3b72`.
- Default native ComfyUI `CheckpointLoaderSimple` **cannot** load the compressed Tiny-SD UNet, even though the file appears in the dropdown.
- Portable baseline x86-64/SSE2-only `stable-diffusion.cpp` was built separately and installed privately in `~/comfyui-isolated/.control/sd-cpp-runtime-sse2`.
- A real **256×256** PNG was generated directly on the VPS by the portable CPU engine in approximately **3 minutes 48 seconds** (2 diffusion steps; run `38658907082`). PNG SHA-256: `8ad21ae1664a0edb142195d78af5ac40fa59f8ba5bac1c40170a824f481cd52a`; factory loop was still alive after the test.
- The first-generation blurred output is a technical test, **not** marketable imagery.
- A `SaeitSafeCPURender` plugin was privately registered in the actual ComfyUI server's `custom_nodes/saeit_safe_cpu`. Registration over the localhost API was verified in run `38659643625` and the server was then stopped.
- Full PNG output through the ComfyUI custom node is a separate QA gate; do not infer it from registration alone.

## Mobile operations with no added account

GitHub Actions workflows already use the owner's authorized GitHub session:

- **ComfyUI VPS Private Lifecycle Control** — `status`, `start`, `stop`, `health`; on-demand timeouts; no Termux.
- **ComfyUI CPU Image Studio - Preset Runner** — four allowlisted sample presets rendered in temporary GitHub runners with downloadable PNG artifacts, independently verified (runs `38655879476`, `38656883582`).
- **ComfyUI VPS Bounded CPU PNG Proof** — safe on-demand 256px demonstration using the private VPS CPU engine; read-only repository access and pinned SSH host key.
- **ComfyUI VPS Native SSE2 Image Node Proof** — optional custom-node experiment controlled through Github, with a bounded ComfyUI session and an explicit factory/RAM watchdog.

No general-purpose arbitrary commands, public HTTP listener, unsecured tunnel or customer prompts are exposed.

## Hardware and safety guardrails

- Startup requires a live factory PID and enough available RAM.
- A single low-priority CPU inference process runs under a memory bound and short timeout. It must terminate if RAM available falls below 975 MiB or factory liveness fails.
- SSH key stays in GitHub Actions Secrets, and the VPS SSH fingerprint is pinned.
- The ComfyUI HTTP server listens only at `127.0.0.1:18188`; custom rendering is local and does not require public port 8188.
- For high-resolution, frequent or sale-quality AI imagery, use a separate GPU service. This old SSE2-only CPU cannot realistically deliver commercial-quality 8K output.
- **Graphical ComfyUI access in the phone's browser** still requires a private authenticated access mechanism (e.g. a tailnet account). GitHub Actions provides authenticated phone-based operations in the meantime.
- The factory's process being alive is **not** evidence that sellable products are ready. Never auto-post test images to stores.

## Critical operational references

- `.github/workflows/comfyui-vps-control.yml`
- `.github/workflows/comfyui-vps-bounded-render.yml`
- `.github/workflows/comfyui-vps-native-node-proof.yml`
- `ops/comfyui-vps/vps_smoke.py`
- `ops/comfyui-vps/saeit_cpu_node/__init__.py`
- `ops/comfyui-vps/run_preset.py`
