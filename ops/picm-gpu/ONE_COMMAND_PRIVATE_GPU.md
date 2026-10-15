# PICM · isolated GPU one-command film pipeline (staged, not live)

**Status: software candidate / CI only.** This does not deploy to MojPlayWin,
attach a GPU, produce a film, rent compute, or touch the autonomous factory.

The October 15 2026 private read-only VPS audit
(https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38774732433)
confirmed that the current 3-vCPU, 3.8-GiB RAM factory VPS has **no
detectable NVIDIA/ROCm GPU**, no ffmpeg/ffprobe and no listening ComfyUI
video service. The existing CPU image workflow is **not** a video model.

## What this stage adds

`story_pipeline.py` safely combines existing local
`story_comfy.py` I2V scene generation with
`story_assemble.py` MP4 composition on a **separate** compatible GPU
machine. It validates the exact owner-staged `<id>.stage.json` +
`<id>.input` pair (owner-specific metadata, 0600, up to 24h old),
checks actual loopback-only ComfyUI GPU state, verifies that the API graph
connects image/text/frame inputs through a generative sampler to a video
output, requires every real rendered clip, then creates one MP4 and
an owner-private SHA-256 receipt. Dry-run never starts ComfyUI or produces
a pretend video.

This graph gate requires a connected `KSampler`, `SamplerCustom`,
`WanVideoSampler`, `LTXVSampler`, `WanSampler` or
`HunyuanVideoSampler`. GPU model graph exports may vary; unfamiliar model
node types must be reviewed and tested rather than bypassing the gate.

## Before *any* production test

- Provision GPU compute independently of the factory VPS, with a
  **locally loaded actual I2V model**, adequate VRAM and storage.
- Install ComfyUI and FFmpeg/FFprobe **on that GPU machine**.
- Bind ComfyUI only to `127.0.0.1:8188`; do not publish an unauthenticated
  model API or SSH port to the public internet.
- Export a real ComfyUI **API-format** I2V workflow and prepare
  `node_map.json` per `README.md`; confirm the model paths and exact sampler
  classes instead of guessing node IDs.
- Transfer the owner-approved input pair over an authenticated, encrypted
  private channel into a 0700 working folder. **Automatic cPanel→GPU
  transfer is not implemented yet.** Do not copy private photos into GitHub
  repositories, Actions artifacts, logs, or open cloud buckets.
- No cloud GPU account, billing agreement, provider key, or rental can be
  inferred from the repository. The owner must explicitly authorize any
  cost-bearing GPU provisioning.

## Private GPU command

Run these commands **only on the isolated GPU machine** with the private
stage pair, valid workflow graph and model already installed:

```sh
umask 077
mkdir -m 700 -p "$HOME/picm-owner-private"
cd /path/to/ops/picm-gpu

# Offline validation: never claims an actual video.
python3 story_pipeline.py \
  --metadata "$HOME/picm-owner-private/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.stage.json" \
  --reference "$HOME/picm-owner-private/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.input" \
  --workflow-api "$HOME/picm-owner-private/wan_i2v_api.json" \
  --node-map "$HOME/picm-owner-private/node_map.json" \
  --workspace "$HOME/picm-owner-private/new-job" \
  --dry-run

# Generate *only* when a real GPU is provisioned and ComfyUI is ready:
python3 story_pipeline.py \
  --metadata "$HOME/picm-owner-private/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.stage.json" \
  --reference "$HOME/picm-owner-private/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.input" \
  --workflow-api "$HOME/picm-owner-private/wan_i2v_api.json" \
  --node-map "$HOME/picm-owner-private/node_map.json" \
  --workspace "$HOME/picm-owner-private/new-job"
```

Replace the placeholder ID with the *actual same* staging identifier in
both filenames. The output folder must be absent before the real run.
The script refuses to reuse an existing output directory, to prevent
cross-job data mixing. Failed partial jobs require a deliberate review
before being discarded or retried in a fresh directory.

After authentic model generation and FFprobe verification, only then will
`new-job/story.mp4` and `new-job/receipt.json` exist. Neither a staged
story, a synthetic CI clip, nor a pan/zoom browser animation qualifies.

### Important unfinished stages

1. Connect the live owner-only cPanel staging queue to a **separate**
   GPU machine using strictly authenticated and encrypted transport.
2. Return the verified MP4 securely to the owner-only PICM download page,
   enforce storage limits, secure deletion and revocation.
3. Perform a **real** 5-second I2V render with a user-approved reference,
   check identity/movement/quality, and only then test 60-second shots.

No live GPU, owner-private MP4 download endpoint, automatic provider
billing or on-demand GPU startup is claimed by this software candidate.
