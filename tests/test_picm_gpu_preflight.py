"""Never confuse CPU or missing GPU models with PICM movie readiness."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "ops" / "picm-gpu"
sys.path.insert(0, str(ROOT))
import gpu_preflight as p

GRAPH = {
    "1": {"class_type": "LoadImage", "inputs": {"image": "old.png"}},
    "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "scene"}},
    "3": {"class_type": "WanImageToVideo", "inputs": {
        "start_image": ["1", 0], "positive": ["2", 0], "length": 81}},
    "4": {"class_type": "KSampler", "inputs": {"latent_image": ["3", 0]}},
    "5": {"class_type": "VAEDecode", "inputs": {"samples": ["4", 0]}},
    "6": {"class_type": "CreateVideo", "inputs": {
        "images": ["5", 0], "fps": 16}},
    "7": {"class_type": "SaveVideo", "inputs": {
        "video": ["6", 0], "filename_prefix": "picm"}},
}
MAP = {"image": "1", "text": "2", "length": "3",
       "fps": "6", "output": "7"}


class PICMIndependentGPUReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.home.chmod(0o700)
        self.graph = self.home / "api.json"
        self.nodes = self.home / "node_map.json"
        self.graph.write_text(json.dumps(GRAPH))
        self.nodes.write_text(json.dumps(MAP))
        self.disk = type("Usage", (), {
            "total": 60 * (1024 ** 3),
            "used": 10 * (1024 ** 3),
            "free": 50 * (1024 ** 3)})()

    def inspect(self, *, response=None, vram="24576, 23000", disk=None):
        response = response or {
            "devices": [{"type": "cuda", "name": "NVIDIA RTX"}]}
        with patch.object(p.shutil, "which", return_value="/usr/bin/ffmpeg"):
            with patch.object(p.shutil, "disk_usage", return_value=disk or self.disk):
                return p.inspect(
                    self.home, self.graph, self.nodes,
                    probe=lambda _: response,
                    gpu_command=lambda: vram)

    def test_real_gpu_and_workflow_ready_is_only_preflight_not_render(self):
        result = self.inspect()
        self.assertTrue(result["ready"], result)
        self.assertEqual(result["state"], "runtime_preflight_ready_not_rendered")
        self.assertNotIn("real_mp4_rendered", str(result))

    def test_cpu_only_is_rejected_even_if_gpu_memory_is_fake(self):
        result = self.inspect(response={"devices": [{
            "type": "cpu", "name": "CPU"}]})
        self.assertFalse(result["ready"])
        self.assertIn("no_local_comfy_gpu", result["requirements"])

    def test_insufficient_gpu_memory_blocks_not_silent_fallback(self):
        result = self.inspect(vram="8192, 7000")
        self.assertFalse(result["ready"])
        self.assertIn("insufficient_free_gpu_vram", result["requirements"])

    def test_unverified_memory_never_assumes_gpu_capacity(self):
        result = self.inspect(vram="broken")
        self.assertFalse(result["ready"])
        self.assertIn("gpu_memory_unverified_nvidia_only", result["requirements"])

    def test_small_disk_rejected(self):
        tiny = type("Usage", (), {"free": 5 * (1024 ** 3)})()
        result = self.inspect(disk=tiny)
        self.assertFalse(result["ready"])
        self.assertIn("insufficient_free_gpu_disk", result["requirements"])

    def test_incorrect_or_missing_model_graph_is_rejected(self):
        self.graph.write_text(json.dumps({
            "1": {"class_type": "LoadImage", "inputs": {"image": "foo"}}}))
        result = self.inspect()
        self.assertFalse(result["ready"])
        self.assertIn("real_connected_i2v_workflow_not_configured",
                      result["requirements"])

    def test_comfy_must_bind_loopback_not_public_network(self):
        with patch.object(p.shutil, "which", return_value="/usr/bin/ffmpeg"):
            with patch.object(p.shutil, "disk_usage", return_value=self.disk):
                result = p.inspect(self.home, self.graph, self.nodes,
                    comfy="http://gpu-provider.example:8188",
                    gpu_command=lambda: "24576, 23000")
        self.assertFalse(result["ready"])
        self.assertIn("loopback_comfy_service_unavailable", result["requirements"])


    def test_wan5b_profile_accepts_8gb_only_when_free_vram_sufficient(self):
        self.assertEqual(p.GPU_PROFILES["wan22-5b-offload-8gb"], 7000)
        response = {"devices": [{"type": "cuda", "name": "NVIDIA RTX 8GB"}]}
        source = json.loads(self.graph.read_text())
        source["3"]["class_type"] = "Wan22ImageToVideoLatent"
        source["9"] = {"class_type": "UNETLoader",
                        "inputs": {"unet_name": "wan2.2_ti2v_5B_fp16.safetensors"}}
        source["4"]["inputs"]["model"] = ["9", 0]
        self.graph.write_text(json.dumps(source))
        with patch.object(p.shutil, "which", return_value="/usr/bin/ffmpeg"):
            with patch.object(p.shutil, "disk_usage", return_value=self.disk):
                def check(minimum):
                    return p.inspect(self.home, self.graph, self.nodes,
                        minimum_gpu_mib=minimum, probe=lambda _: response,
                        gpu_profile="wan22-5b-offload-8gb" if minimum == 7000
                            else "standard-24gb",
                        gpu_command=lambda: "8192, 7400")
                self.assertFalse(check(p.GPU_PROFILES["standard-24gb"])["ready"])
                self.assertTrue(check(p.GPU_PROFILES["wan22-5b-offload-8gb"])["ready"])

    def test_wan5b_profile_rejects_gpu_with_low_free_memory(self):
        with patch.object(p.shutil, "which", return_value="/usr/bin/ffmpeg"):
            with patch.object(p.shutil, "disk_usage", return_value=self.disk):
                result = p.inspect(self.home, self.graph, self.nodes,
                    minimum_gpu_mib=p.GPU_PROFILES["wan22-5b-offload-8gb"],
                    gpu_profile="wan22-5b-offload-8gb",
                    probe=lambda _: {"devices": [{"type": "cuda"}]},
                    gpu_command=lambda: "8192, 4900")
        self.assertFalse(result["ready"])
        self.assertIn("insufficient_free_gpu_vram", result["requirements"])

    def test_low_vram_profile_rejects_unrelated_14b_workflow(self):
        with patch.object(p.shutil, "which", return_value="/usr/bin/ffmpeg"):
            with patch.object(p.shutil, "disk_usage", return_value=self.disk):
                result = p.inspect(
                    self.home, self.graph, self.nodes,
                    minimum_gpu_mib=7000, gpu_profile="wan22-5b-offload-8gb",
                    probe=lambda _: {"devices": [{"type": "cuda"}]},
                    gpu_command=lambda: "8192, 7400")
        self.assertFalse(result["ready"])
        self.assertIn("wan22_5b_checkpoint_not_selected_in_workflow",
                      result["requirements"])

    def test_disconnected_5b_checkpoint_does_not_bypass_model_gate(self):
        graph = json.loads(self.graph.read_text())
        graph["9"] = {"class_type": "UNETLoader",
                      "inputs": {"unet_name": "wan2.2_ti2v_5B_fp16.safetensors"}}
        graph["3"]["class_type"] = "Wan22ImageToVideoLatent"
        self.graph.write_text(json.dumps(graph))
        with patch.object(p.shutil, "which", return_value="/usr/bin/ffmpeg"):
            with patch.object(p.shutil, "disk_usage", return_value=self.disk):
                result = p.inspect(
                    self.home, self.graph, self.nodes,
                    minimum_gpu_mib=7000, gpu_profile="wan22-5b-offload-8gb",
                    probe=lambda _: {"devices": [{"type": "cuda"}]},
                    gpu_command=lambda: "8192, 7400")
        self.assertFalse(result["ready"])
        self.assertIn("wan22_5b_checkpoint_not_selected_in_workflow",
                      result["requirements"])

if __name__ == "__main__":
    unittest.main()
