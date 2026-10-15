# PICM private multi-shot film — independent GPU worker

## What is deployed vs what is not

The owner-only website at `/picm/workspace/` can accept one private
reference image and a story, split it into 5/10/30/60-second shot plans, and
store the plan. No authentic AI movie is produced on the hosting VPS yet.
Old browser pan/zoom remains a separately labeled non-generative option.

These scripts prepare the GPU-dependent remainder:

- `story_comfy.py` — send each shot with the reference photo and story
  action to an **actual local ComfyUI image-to-video workflow**, then download
  and ffprobe-check the generated MP4 clips.
- `story_assemble.py` — require **every real generated clip**, normalize the
  shots, and concatenate into one private MP4 of the requested duration.
  No still-image camera moves, placeholders, silent synthetic completion,
  fabricated results or fake success notifications are allowed.

These two GPU scripts are **not** installed by the cPanel deployment.
They must execute on separate, appropriately provisioned GPU hardware, not
the live MojPlayWin/PICM hosting VPS and not the autonomous product factory.

## Required runtime (not yet provided)

- A machine with a compatible actual GPU, enough VRAM, storage and compute
  capacity to run a modern local image-to-video model (e.g. ComfyUI Wan2.2).
- ComfyUI bound **only** to 127.0.0.1 and loaded with actual model weights.
- An **API-format** image-to-video workflow exported from that installed
  version of ComfyUI, with LoadImage, prompt text, frame count and SaveVideo
  output nodes accessible in the workflow graph.
- Python 3.11+ and FFmpeg/FFprobe installed **on the isolated GPU machine**.
- Secure private transport of owner-authenticated photo/plan to that machine;
  never expose the model port to the public internet.

Reference: official ComfyUI Wan2.2 I2V workflow:
https://github.com/Comfy-Org/ComfyUI/blob/master/blueprints/Image%20to%20Video%20%28Wan%202.2%29.json

GPU hardware and free/paid compute capacity are separate from the open-source
software license. There is no guarantee of unlimited free 60-second rendering.

## Node map

Create a private file `node_map.json` with the corresponding **actual**
node IDs from your chosen exported API graph:

```json
{
  "image": "load_image_node_id",
  "text": "prompt_node_id",
  "length": "video_length_node_id",
  "fps": "create_video_node_id",
  "output": "save_video_node_id"
}
```

`fps` is optional if your exported workflow has no fps input. The mapped
inputs must be exactly `image`, `text`, `length`, and optionally `fps`.
The mapping is model/workflow-version-specific. The script intentionally
refuses to guess IDs or treat a normal ComfyUI canvas export as an API graph.

## Execution after a compatible GPU is actually ready

Copy one private staged metadata file and its corresponding reference image
securely to the independent GPU machine. Keep both outside any web root, and
give the owner/worker exclusive filesystem access.

```bash
# Validate the planned shots and graph *without* generating a fake film.
python story_comfy.py \
  --metadata /private/story.stage.json \
  --reference /private/owner-reference.input \
  --workflow-api /private/wan_i2v_api.json \
  --node-map /private/node_map.json \
  --clips /private/generated-scenes \
  --dry-run

# ONLY once the independent GPU, model and local ComfyUI exist:
python story_comfy.py \
  --metadata /private/story.stage.json \
  --reference /private/owner-reference.input \
  --workflow-api /private/wan_i2v_api.json \
  --node-map /private/node_map.json \
  --clips /private/generated-scenes \
  --comfy http://127.0.0.1:8188

# Only after all real clips have passed validation:
python story_assemble.py \
  --metadata /private/story.stage.json \
  --clips /private/generated-scenes \
  --output /private/final-story.mp4
```

The image-to-video adapter uses 16 frames per second by default and requests
`duration * 16 + 1` latent frames per shot; adapt to the selected model if
its duration contract differs. ComfyUI render results may be shorter, may
fail, or may not maintain the character identity perfectly. The assembler
rejects shortened or missing footage rather than fabricating it.

## Privacy & factory safety

- Only loopback HTTP ComfyUI URLs permitted; all HTTP redirects refused.
- No uploads to public cloud, no requirement for Tailscale, no new open port.
- All private scene clips and final movie written with mode `0600`.
- Real video streams and durations checked with FFprobe.
- Existing unrelated factory services and website routes must remain intact.
- No fixed daily story submission count; only actual finite capacity.
- Staged photo inputs expire after 24h on hosting. GPU transfer and cleanup
  require an independently authorized, owner-only worker integration.
- None of the new GPU-worker scripts automatically starts ComfyUI or connects
  to the live private owner website. That final handoff remains unimplemented.

## Tests

```bash
python -m pytest -q tests/test_picm_storyboard.py \
  tests/test_picm_story_assemble.py tests/test_picm_story_comfy.py
```
