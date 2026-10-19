# PICM owner-only HTTPS GPU handoff · staged candidate

**Deployment: NOT PERFORMED. Real AI video: NOT YET AVAILABLE.**
The actual MojPlayWin URL and existing private owner login remain unchanged.
Only the \`Saeit\` PR development branch contains these proposed routes.

## Verified hardware blocker

2026-10-15 read-only audit of the currently connected VPS:
https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38774732433

- No NVIDIA / ROCm GPU device or working driver detected.
- About 3 logical CPUs, 3.8 GiB RAM, 26 GiB free disk.
- FFmpeg/FFprobe not installed; ComfyUI not listening.
- Existing CPU image-generation service is **not** a generative I2V video engine.

**Do not run the GPU video renderer on the autonomous product-factory VPS.**

## Architecture after a compatible independent GPU is provisioned

1. Owner logs into \`/picm/login/\` and sends an image and story. The current
   \`picm_reference_stage\` stores \`<id>.input\` and \`<id>.stage.json\` under
   private cPanel storage, not the document root.
2. A distinct GPU host running \`video_worker_client.py\` performs its own
   GPU/model preflight **before** claiming a job. It polls:
   \`GET /picm/video/worker/next/\`.
3. The GPU worker uses a separate random 0600 \`gpu-worker-token\` and
   short-lived, UUID-format per-job lease to retrieve metadata and image
   via certificate-verified **https://mojplaywin.com**. It never asks the
   owner to leave Termux running or publicly exposes ComfyUI.
4. A truly local GPU ComfyUI I2V model generates *each* animated clip.
   \`story_pipeline.py\` and FFprobe require real video streams and assemble
   the validated duration into a single private MP4.
5. The GPU worker rehashes the output and returns it to the site in
   at-most-1-MiB HTTPS chunks; offsets, total bytes, SHA-256, owner binding,
   lease, duration and final receipt are checked before atomic commit.
   The cPanel host validates the MP4 container header and SHA-256; it
   **does not** perform independent visual-quality assessment or FFprobe
   itself. It relies on the trusted GPU worker's FFprobe proof.
6. Only that PICM owner can visit
   \`/picm/video/status/<id>/\` and download at
   \`/picm/video/download/<id>/\`. The browser never sees bearer credentials.

## Candidate API routes (not live)

Import \`django.urls.include\` and **only on the confirmed MojPlayWin Django
host**, after verifying no existing route collision, add:

\`\`\`python
urlpatterns += [
    path("", include("core.picm_video_urls")),
]
\`\`\`

This must use the host's existing PICM atomic-backup/rollback rollout, never
overwrite the whole URL routing or site. Do **not** append to unrelated
Zomorod Melal website routing or factory services. No deploy workflow is
enabled by this staged PR.

## Worker secrets (future, not executed)

- Mint a unique strong token in private storage
  \`/home/zomorod2/.picm-queue/gpu-worker-token\`, chmod 0600.
  It is **not** the existing image-CPU worker token.
- Install the same token on the independent GPU node in a 0600 local file
  using owner-authorized encrypted transfer. Never commit it to GitHub,
  put it in workflow logs, query parameters, screenshots or public files.
- Ensure \`/picm/video/worker/next/\` returns HTTP 403 without that token
  before activating any real GPU worker.
- The provider's billing and any credential creation require separate
  account ownership and authorization. No rental or provider API call occurs
  in the repository code.

## On an already provisioned separate GPU node

Install real ComfyUI with a compatible I2V workflow, model weights,
FFmpeg and FFprobe; bind the ComfyUI API **only** to \`127.0.0.1:8188\`.
Export \`workflow_api.json\` and \`node_map.json\` with real matching node IDs
following \`ops/picm-gpu/README.md\`. Place configuration and token files
in private 0700 directories with 0600 file modes.

\`\`\`bash
umask 077
install -d -m 700 "$HOME/picm-owner-work"
cd /path/to/Saeit/ops/picm-gpu
python3 video_worker_client.py \
  --private-dir "$HOME/picm-owner-work" \
  --token-file "$HOME/private/gpu-worker-token" \
  --workflow-api "$HOME/private/workflow_api.json" \
  --node-map "$HOME/private/node_map.json"
\`\`\`

This is one-job-at-a-time. It is deliberately not a permanently running
daemon, and the model cannot be claimed ready by a CPU-only ComfyUI.
Do not leave private files in a public web root. Unsuccessful jobs require
inspection and safe cleanup on the dedicated GPU worker; successful jobs'
local scratch copies are unlinked after the cPanel server acknowledges
delivery (this is **not** a secure erase guarantee).

## Limits and remaining release gates

- Staged original photo/metadata expires in 24h.
- Per-job lease expires after 8h. A long production render requires
  tested renewal or sufficiently fast model execution before activation.
- A verified MP4 is available to the owner for 48h, then cleaned by the
  bridge's next maintenance pass. The client must save the download in time.
- 1 active GPU transfer, max 1 MiB/chunk, max 128 MiB final MP4 on cPanel;
  **not** a fixed story-count quota. Storage/VRAM/compute are finite.
- A real 5-second private reference render, owner login download proof,
  model/provider authorization, safe deployment backup, hardening, and
  60-second story evaluation are **still pending**.

## Offline tests, not GPU evidence

\`\`\`bash
pytest -q tests/test_picm_video_bridge.py tests/test_picm_video_worker_client.py
python -m unittest discover -s tests -p 'test_picm_story_pipeline.py' -v
\`\`\`

These tests use synthetic inputs and fake transport acknowledgments. They
verify authorization, no unauthorized photo transfer, chunk integrity and
correct handling of missing GPU. A green test suite cannot prove real model
availability, visual identity consistency, or a 60-second AI film.


## Wan2.2 5B lower-VRAM profile (optional, not a runtime guarantee)

The official ComfyUI Wan2.2 guide describes the 5B TI2V workflow as
supporting roughly 8GB NVIDIA GPU VRAM with ComfyUI's native CPU offloading.
That is a CONDITIONAL model-specific case, **not** a promise that every
8GB GPU can render a smooth, 60-second film:
https://docs.comfy.org/tutorials/video/wan/wan2_2

Select the 5B profile only if your **exported ComfyUI API graph** really
connects the `wan2.2_ti2v_5B` `UNETLoader` through
`Wan22ImageToVideoLatent`, a sampler, and `SaveVideo`.
The preflight refuses decoy/disconnected model nodes or an unrelated
14B workflow even if the driver reports ample free VRAM.

On a separately provisioned GPU host, BEFORE claiming any owner job:

```bash
cd /path/to/Saeit/ops/picm-gpu
python3 gpu_preflight.py \
  --work-dir "$HOME/picm-owner-work" \
  --workflow-api "$HOME/private/workflow_api.json" \
  --node-map "$HOME/private/node_map.json" \
  --gpu-profile wan22-5b-offload-8gb
```

After successful readiness checks, the one-job private worker accepts
the same explicit model profile:

```bash
python3 video_worker_client.py \
  --private-dir "$HOME/picm-owner-work" \
  --token-file "$HOME/private/gpu-worker-token" \
  --workflow-api "$HOME/private/workflow_api.json" \
  --node-map "$HOME/private/node_map.json" \
  --gpu-profile wan22-5b-offload-8gb
```

The default conservative profile remains `standard-24gb`.
The script does not download model weights, install a GPU driver, purchase
GPU hours, guarantee compatible CPU RAM, or prove a real AI movie.
Every GPU-side model and video output still needs a real 5-second test.
