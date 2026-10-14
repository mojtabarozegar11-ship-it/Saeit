"""Saeit CPU-only image rendering node for private ComfyUI.

Uses an isolated low-RAM CLI backend; no shell, sudo, public port or factory changes.
"""
import fcntl
import hashlib
import os
from pathlib import Path
import resource
import signal
import subprocess
import tempfile
import time

import numpy as np
import torch
from PIL import Image

HOME = Path.home()
ROOT = HOME / "comfyui-isolated"
BIN_DIR = ROOT / ".control/sd-cpp-runtime/bin"
BIN = BIN_DIR / "sd-cli"
MODEL = ROOT / "source-v0.40.0/models/checkpoints/segmind_tiny_sd_candidate.safetensors"
STATE = ROOT / ".control/qa-render"
EXPECTED_SHA256 = "92e00b860c409f8cfc521a94f779009c6ebd28bf07670bf50e747682ab7b3b72"
FACTORY_PID = HOME / "factory-runtime/operations/vps-only-loop.pid"


def factory_running():
    try:
        os.kill(int(FACTORY_PID.read_text().strip()), 0)
        return True
    except (OSError, ValueError):
        return False


def available_kib():
    with open("/proc/meminfo", "r", encoding="ascii") as fp:
        for line in fp:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1])
    return 0


def resource_guard():
    os.nice(17)
    limit = 2_850_000_000
    resource.setrlimit(resource.RLIMIT_DATA, (limit, limit))


def validated_files():
    if not BIN.is_file() or not os.access(BIN, os.X_OK):
        raise RuntimeError("Saeit CPU backend has not been installed")
    if not MODEL.is_file() or MODEL.is_symlink():
        raise RuntimeError("Private Tiny-SD checkpoint not installed")
    h = hashlib.sha256()
    with MODEL.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    if h.hexdigest() != EXPECTED_SHA256:
        raise RuntimeError("Checkpoint integrity check failed")


class SaeitSafeCPURender:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "prompt": ("STRING", {"multiline": True, "default": "Green shoots on a sunny farm"}),
            "steps": ("INT", {"default": 4, "min": 1, "max": 8}),
            "seed": ("INT", {"default": 42, "min": 0, "max": 2147483647}),
            "cfg": ("FLOAT", {"default": 7.0, "min": 1.0, "max": 12.0, "step": 0.5}),
        }}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "render"
    CATEGORY = "Saeit / Protected CPU"

    def render(self, prompt, steps, seed, cfg):
        prompt = str(prompt).strip()
        if not (1 <= len(prompt) <= 600):
            raise ValueError("Prompt length must be 1–600 characters")
        validated_files()
        if not factory_running() or available_kib() < 2_900_000:
            raise RuntimeError("Safe resource or factory requirement not met")
        STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(STATE, 0o700)
        with (STATE / "qa.lock").open("w") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("Another CPU render is already running") from exc
            with tempfile.TemporaryDirectory(dir=str(STATE), prefix=".node-") as temp:
                output = Path(temp) / "result.png"
                env = dict(os.environ, LD_LIBRARY_PATH=str(BIN_DIR), OMP_NUM_THREADS="1",
                           OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", MALLOC_ARENA_MAX="2")
                argv = [str(BIN), "-m", str(MODEL), "-p", prompt,
                        "-W", "512", "-H", "512", "--steps", str(steps),
                        "--seed", str(seed), "--cfg-scale", str(cfg),
                        "--sampling-method", "euler_a", "--diffusion-fa",
                        "--log-level", "error", "-o", str(output)]
                with tempfile.TemporaryFile() as log:
                    child = subprocess.Popen(argv, stdin=subprocess.DEVNULL,
                                             stdout=log, stderr=subprocess.STDOUT,
                                             cwd=str(STATE), env=env,
                                             start_new_session=True, preexec_fn=resource_guard)
                    end = time.monotonic() + 240
                    try:
                        while child.poll() is None and time.monotonic() < end:
                            if not factory_running() or available_kib() < 950_000:
                                raise RuntimeError("Render stopped by RAM/factory guard")
                            time.sleep(0.25)
                        if child.poll() is None:
                            raise RuntimeError("Private CPU render exceeded its time budget")
                        if child.returncode:
                            raise RuntimeError("Private CPU renderer failed")
                        if not output.is_file():
                            raise RuntimeError("No generated image received")
                        with Image.open(output) as raw:
                            pixels = np.asarray(raw.convert("RGB"), dtype=np.float32) / 255.0
                        if pixels.shape != (512, 512, 3):
                            raise RuntimeError("Unexpected CPU output resolution")
                        result = torch.from_numpy(pixels).unsqueeze(0)
                        return (result,)
                    finally:
                        if child.poll() is None:
                            os.killpg(child.pid, signal.SIGTERM)
                            try:
                                child.wait(timeout=8)
                            except subprocess.TimeoutExpired:
                                os.killpg(child.pid, signal.SIGKILL)
                                child.wait(timeout=8)


NODE_CLASS_MAPPINGS = {"SaeitSafeCPURender": SaeitSafeCPURender}
NODE_DISPLAY_NAME_MAPPINGS = {"SaeitSafeCPURender": "Saeit Safe CPU Image"}
