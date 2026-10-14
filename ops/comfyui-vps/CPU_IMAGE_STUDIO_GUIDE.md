# Saeit CPU Image Studio — practical operations

The validated image-generation backend is a SHA-pinned `stable-diffusion.cpp` executable on a disposable Ubuntu GitHub Actions runner. This **does not** use the standard ComfyUI checkpoint loader: the available compressed Tiny-SD checkpoint cannot load in that node.

## Generate an image from a mobile device, without Termux

1. With your already-authorized GitHub account, open **Actions** → **ComfyUI CPU Image Studio - Preset Runner** in the Saeit repository.
2. Select **Run workflow**. Pick `orchard`, `greenhouse`, `product`, or `abstract`; pick 4, 8 or 12 sampling steps.
3. Open the completed run. Under **Artifacts**, download **comfyui-cpu-companion-512px-proof**.
4. The ZIP contains a verifiable 512×512 PNG. It is **not** an 8K or production-quality image.

No VPS traffic, Termux app, phone boot automation, ComfyUI public port, GPU account, Tailscale account, token, private prompt, or external credentials are required for this workflow. Inputs are allowlisted presets, not executable commands.

The worker downloads and SHA-256 verifies the exact engine and model at each run and exits at job completion. Its action has read-only repository permission. Its output is retained for seven days.

## Verified evidence

- GitHub-runner CPU image proof `38655879476`: passed, produced a real 512×512 PNG with SHA-256 `44a3375a3790c4212228b4e720fd7df6f9624a9ea1cf12d322c67a5d7767c71e`, artifact `11936762212`.
- VPS ComfyUI CPU HTTP and model selector API `38654614841`: passed.
- Native ComfyUI inference `38655021890`: failed due to incompatible Tiny-SD UNet checkpoint architecture. This is a *known limitation*, not a successful image render.
- VPS companion executable `38656666595`: compatible private binary plus OpenMP library checked; executable help returns success.
- Running standalone 512×512 inference **on the VPS** is not yet end-to-end verified.

## Safety and scope

- The already-running factory remains operational but this is not a claim that its products are commercially ready.
- Phone **graphical ComfyUI canvas** requires private access authentication; without account enrollment, it is not available. Use GitHub Actions for the currently verified image request/delivery workflow.
- The Tiny-SD model is a **technical proof**. License / model-card restrictions apply. Do not auto-sell or deploy generated images as catalog products without human quality review.
- Prefer an independent GPU image-generation worker for professional high-resolution commercial production. The three-core / 3.8 GiB VPS should not host heavy diffusion inference alongside the live factory.

## Source paths

- `.github/workflows/comfyui-cpu-runner-image-proof.yml`
- `ops/comfyui-vps/quality_gate.py`
- `ops/comfyui-vps/install_tiny_model.sh`
- `.github/workflows/comfyui-model-readiness-audit.yml`
