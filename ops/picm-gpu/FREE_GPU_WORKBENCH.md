# PICM free-GPU experimental workbench

**Not an in-place repair of the VPS or a newly deployed video generation service.** The existing 3-core CPU-only VPS still hosts the protected 256px image renderer. Authentic person animation and neural photo enhancement are offered in an **optional external notebook** requiring the owner's action.

## Run on a phone

1. Open the [PICM free-GPU Colab notebook](https://colab.research.google.com/github/mojtabarozegar11-ship-it/Saeit/blob/main/ops/picm-gpu/PICM_Free_GPU_Video_and_AI_Upscale.ipynb).
2. In Colab, choose **Runtime → Change runtime type → GPU**. Do not choose a paid plan; free GPU capacity is not guaranteed.
3. Run the notebook cells in sequence and upload an authorized photo directly into the Colab session.
4. For *actual subject movement*, run the LTX image-to-video section and download the generated MP4, if the GPU has enough VRAM. First try 49 frames (approximately 6 seconds at 8 fps); choose 81 frames for approximately 10 seconds if your allocation supports it. A failed/aborted run is not a movie.
5. For *AI image enhancement*, run the Real-ESRGAN 4× section. An optional final Lanczos resize can provide an **8K-sized** PNG. This is explicitly **not native 8K detail**.

The notebook does **not** connect to the live PICM user account, save to MojPlayWin, automatically upload private images to public GitHub Actions artifacts, install server packages, change a payment system, or charge a service. All required outputs must be verified by the notebook before any download is offered.

## Limits

- Google Colab free GPU allocation is dynamic, may be unavailable, and is subject to its fair-use policies.
- LTX may need GPU memory above free allocations, and can fail or alter faces/hands. It uses actual video diffusion frames when it succeeds, not pan/zoom.
- Real-ESRGAN enhances estimated detail. A resized 7680×4320 canvas cannot promise restoration of true lost facial information.
- The public GitHub repository contains notebook **code only**, never user's photo. The user decides whether to upload a photo to Google Colab.
- **Commercial deployment remains blocked** until a private stable GPU provider is available, rights/licensing are reviewed, final artifacts pass independent QC, and the private PICM handoff is implemented and tested.

For the existing site's protected experimental image generator visit [PICM login](https://mojplaywin.com/picm/login/).
