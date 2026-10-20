"""Private PICM CPU fallback contract tests. No model or network needed."""
import importlib.util
import io
import os
from pathlib import Path
import struct
import tempfile
from unittest.mock import patch

import pytest

WORKER = Path(__file__).resolve().parents[1] / "ops/picm-vps/worker.py"
spec = importlib.util.spec_from_file_location("picm_private_worker", WORKER)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)

PNG = (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR"
       + struct.pack(">II", 256, 256) + b"\x00" * 1200)
JOB = {"id": "a" * 32, "lease": "b" * 32, "prompt": "Healthy green garden",
       "steps": 1}


def test_prefers_verified_low_resource_cpu_path_without_comfyui():
    with patch.object(worker, "direct_cpu_ready", return_value=True), \
         patch.object(worker, "render_direct_cpu", return_value=PNG) as cpu, \
         patch.object(worker, "start_comfy_if_needed", side_effect=AssertionError("must not start")):
        assert worker.render(JOB) == PNG
        cpu.assert_called_once_with("Healthy green garden", 1)


def test_invalid_job_never_enters_any_backend():
    with patch.object(worker, "direct_cpu_ready", side_effect=AssertionError("should never check")):
        with pytest.raises(RuntimeError, match="INVALID_JOB"):
            worker.render({**JOB, "lease": "malformed"})


def test_tampered_cpu_model_is_rejected_before_rendering():
    with tempfile.TemporaryDirectory() as home:
        exe = Path(home) / "sd-cli"
        model = Path(home) / "checkpoint.safetensors"
        exe.write_text("#!/bin/sh\nexit 0\n")
        exe.chmod(0o700)
        model.write_bytes(b"not the trusted checkpoint")
        with patch.object(worker, "CPU_BIN", exe), patch.object(worker, "CPU_MODEL", model):
            with pytest.raises(RuntimeError, match="PICM_CPU_MODEL_INTEGRITY_FAILURE"):
                worker.direct_cpu_ready()


def test_missing_cpu_install_retains_original_local_comfyui_route():
    calls = []
    def api(endpoint, data=None, timeout=20):
        calls.append(endpoint)
        if endpoint == "/prompt":
            return {"prompt_id": "cpu-history-test"}
        return {"cpu-history-test": {"outputs": {"2": {"images": [{"filename": "test.png"}]}}}}
    with patch.object(worker, "direct_cpu_ready", return_value=False), \
         patch.object(worker, "start_comfy_if_needed") as init, \
         patch.object(worker, "factory_ok", return_value=True), \
         patch.object(worker, "ram_ok", return_value=True), \
         patch.object(worker, "comfy_api", side_effect=api), \
         patch.object(worker, "urlopen", return_value=io.BytesIO(PNG)):
        assert worker.render(JOB) == PNG
        init.assert_called_once()
        assert calls == ["/prompt", "/history/cpu-history-test"]


def test_direct_cpu_executes_command_as_argument_vector_and_validates_png():
    with tempfile.TemporaryDirectory() as base:
        requested = []
        class FakeChild:
            returncode = 0
            pid = 1
            def poll(self):
                return 0
        def fake_spawn(args, **kwargs):
            requested.append((args, kwargs))
            Path(args[-1]).write_bytes(PNG)
            return FakeChild()
        with patch.object(worker, "CPU_STATE", Path(base) / "renders"), \
             patch.object(worker, "factory_ok", return_value=True), \
             patch.object(worker, "ram_ok", return_value=True), \
             patch.object(worker.subprocess, "Popen", side_effect=fake_spawn):
            assert worker.render_direct_cpu("Gentle morning scene", 1) == PNG
        args, kwargs = requested[0]
        assert args[args.index("-p") + 1] == "Gentle morning scene"
        assert args[args.index("--steps") + 1] == "1"
        assert kwargs["start_new_session"] is True
        assert "shell" not in kwargs
        assert kwargs["stdin"] == worker.subprocess.DEVNULL


def test_direct_cpu_never_starts_if_factory_safety_fails():
    with patch.object(worker, "factory_ok", return_value=False), \
         patch.object(worker.subprocess, "Popen", side_effect=AssertionError("must not spawn")):
        with pytest.raises(RuntimeError, match="PICM_CPU_START_GUARD"):
            worker.render_direct_cpu("A quiet garden", 1)
