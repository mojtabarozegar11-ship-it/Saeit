"""Offline and isolated tests for ComfyUI real AI video-scene adapter."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

GPU_DIR = Path(__file__).resolve().parents[1] / "ops" / "picm-gpu"
sys.path.insert(0, str(GPU_DIR))
spec = importlib.util.spec_from_file_location("picm_gpu_comfy", GPU_DIR / "story_comfy.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

GRAPH = {
    "1": {"class_type": "LoadImage", "inputs": {"image": "before.png"}},
    "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "old"}},
    "3": {"class_type": "WanImageToVideo", "inputs": {"length": 81}},
    "4": {"class_type": "CreateVideo", "inputs": {"fps": 16}},
    "5": {"class_type": "SaveVideo", "inputs": {"filename_prefix": "private"}},
}
NODES = {"image": "1", "text": "2", "length": "3", "fps": "4", "output": "5"}
SHOT = {"shot": 1, "duration": 6, "action": "شخص از خواب بیدار می‌شود"}


class ComfyStoryAdapterTests(unittest.TestCase):
    def test_loopback_only_cannot_upload_private_image_to_public_host(self):
        for invalid in ("http://example.com:8188", "https://127.0.0.1:8188",
                        "http://127.0.0.1:8188/other", "http://a@localhost:8188",
                        "http://localhost:8188/?redirect=http://evil.com"):
            with self.assertRaises(m.AssemblyError):
                m.validate_local_url(invalid)
        self.assertEqual(m.validate_local_url("http://127.0.0.1:8188"),
                         "http://127.0.0.1:8188")

    def test_shots_patch_image_action_and_duration_for_real_i2v(self):
        output = m.set_scene_inputs(GRAPH, NODES, SHOT, "owned-photo.png", 16)
        self.assertEqual(output["1"]["inputs"]["image"], "owned-photo.png")
        self.assertIn("خواب", output["2"]["inputs"]["text"])
        self.assertEqual(output["3"]["inputs"]["length"], 97)
        self.assertEqual(output["4"]["inputs"]["fps"], 16)
        self.assertEqual(GRAPH["1"]["inputs"]["image"], "before.png")

    def test_requires_genuine_api_export_and_all_node_mappings(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            workflow = root / "workflow_api.json"
            mapping = root / "node_map.json"
            workflow.write_text(json.dumps(GRAPH))
            mapping.write_text(json.dumps(NODES))
            returned, ids = m.load_workflow(workflow, mapping)
            self.assertEqual(ids["output"], "5")
            self.assertEqual(returned["3"]["inputs"]["length"], 81)
            mapping.write_text(json.dumps({"image": "1"}))
            with self.assertRaises(m.AssemblyError):
                m.load_workflow(workflow, mapping)

    def test_cpu_does_not_claim_video_rendered(self):
        with patch.object(m, "http_json", return_value={
            "devices": [{"type": "cpu", "name": "Intel Xeon CPU"}]}):
            with self.assertRaisesRegex(m.AssemblyError, "actual_GPU_required"):
                m.check_gpu("http://127.0.0.1:8188")

    def test_missing_video_output_is_failure(self):
        response = {"abc": {"status": {"completed": True}, "outputs": {"5": {}}}}
        with patch.object(m, "http_json", return_value=response):
            with self.assertRaisesRegex(m.AssemblyError, "without_real_MP4"):
                m.await_video("http://127.0.0.1:8188", "abc", "5", 10)

    def test_video_metadata_from_native_savevideo(self):
        response = {"abc": {"status": {"completed": True}, "outputs": {"5": {
            "videos": [{"filename": "scene_00001.mp4",
                        "subfolder": "picm", "type": "output"}]}}}}
        with patch.object(m, "http_json", return_value=response):
            self.assertEqual(m.await_video("http://127.0.0.1:8188", "abc", "5", 10),
                             ("scene_00001.mp4", "picm"))


if __name__ == "__main__":
    unittest.main()
