"""Offline safety gates for the private GPU-only PICM movie pipeline."""
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

GPU_ROOT = Path(__file__).resolve().parents[1] / "ops" / "picm-gpu"
sys.path.insert(0, str(GPU_ROOT))
import story_pipeline as pipeline

JOB_ID = "a" * 32
GRAPH = {
    "1": {"class_type": "LoadImage", "inputs": {"image": "old.png"}},
    "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "old"}},
    "3": {"class_type": "WanImageToVideo", "inputs": {
        "start_image": ["1", 0], "positive": ["2", 0], "length": 81}},
    "4": {"class_type": "KSampler", "inputs": {"latent_image": ["3", 0]}},
    "5": {"class_type": "VAEDecode", "inputs": {"samples": ["4", 0]}},
    "6": {"class_type": "CreateVideo", "inputs": {
        "images": ["5", 0], "fps": 16}},
    "7": {"class_type": "SaveVideo", "inputs": {
        "video": ["6", 0], "filename_prefix": "picm"}},
}
NODES = {"image": "1", "text": "2", "length": "3",
         "fps": "6", "output": "7"}


class PrivateGPUStoryPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.metadata = self.root / (JOB_ID + ".stage.json")
        self.photo = self.root / (JOB_ID + ".input")
        self.workflow = self.root / "workflow.json"
        self.mapping = self.root / "nodes.json"
        self.workspace = self.root / "new-private-output"
        self.data = {
            "id": JOB_ID, "user_id": 27, "mode": "story_video",
            "created": time.time(), "state": "staged_awaiting_gpu",
            "storyboard": {
                "duration": 5, "ratio": "16:9",
                "scenes": [{"shot": 1, "start": 0, "end": 5,
                            "duration": 5, "action": "wakes up"}],
                "actual_video_ready": False
            },
        }
        self.metadata.write_text(json.dumps(self.data))
        self.photo.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 300)
        self.workflow.write_text(json.dumps(GRAPH))
        self.mapping.write_text(json.dumps(NODES))
        for file in (self.metadata, self.photo, self.workflow, self.mapping):
            file.chmod(0o600)

    def invoke(self, **kwargs):
        return pipeline.process(self.metadata, self.photo, self.workflow,
                                self.mapping, self.workspace, **kwargs)

    def test_valid_configuration_is_not_misrepresented_as_generated_video(self):
        result = self.invoke(dry_run=True)
        self.assertEqual(result["state"], "configuration_validated_not_rendered")
        self.assertEqual(result["duration"], 5)
        self.assertFalse(self.workspace.exists())

    def test_cpu_or_absent_gpu_cannot_create_mp4_or_even_output_directory(self):
        with patch.object(pipeline, "check_gpu",
                          side_effect=pipeline.AssemblyError("actual_GPU_required")):
            with self.assertRaisesRegex(pipeline.AssemblyError, "actual_GPU_required"):
                self.invoke()
        self.assertFalse(self.workspace.exists())

    def test_reject_passthrough_or_image_only_video_graph(self):
        graph = json.loads(self.workflow.read_text())
        graph["4"]["class_type"] = "ImageSharpen"
        self.workflow.write_text(json.dumps(graph))
        with self.assertRaisesRegex(pipeline.AssemblyError,
                                    "no_connected_generative_video_sampler"):
            self.invoke(dry_run=True)

    def test_require_reference_photo_and_text_both_connected_to_video(self):
        graph = json.loads(self.workflow.read_text())
        graph["3"]["inputs"].pop("start_image")
        self.workflow.write_text(json.dumps(graph))
        with self.assertRaisesRegex(pipeline.AssemblyError, "not_connected"):
            self.invoke(dry_run=True)

    def test_expired_owner_input_is_not_rendered(self):
        self.data["created"] = time.time() - 2 * 86400
        self.metadata.write_text(json.dumps(self.data))
        with self.assertRaisesRegex(pipeline.AssemblyError, "expired"):
            self.invoke(dry_run=True)

    def test_mismatched_reference_rejected(self):
        alternate = self.root / ("b" * 32 + ".input")
        self.photo.rename(alternate)
        with self.assertRaises((OSError, pipeline.AssemblyError)):
            pipeline.validate_stage(self.metadata, alternate)

    def test_reference_symlink_rejected(self):
        alternate = self.root / "original.png"
        self.photo.rename(alternate)
        self.photo.symlink_to(alternate)
        with self.assertRaisesRegex(pipeline.AssemblyError, "private_regular"):
            self.invoke(dry_run=True)

    def test_unsafe_world_readable_photo_rejected(self):
        self.photo.chmod(0o644)
        with self.assertRaisesRegex(pipeline.AssemblyError, "private_regular"):
            self.invoke(dry_run=True)

    def test_remote_comfy_address_cannot_receive_owner_photo(self):
        with self.assertRaisesRegex(pipeline.AssemblyError, "local_loopback"):
            self.invoke(comfy="https://remote-gpu-provider.example:8188")

    def test_no_reuse_of_preexisting_output_folder(self):
        self.workspace.mkdir()
        with patch.object(pipeline, "check_gpu", return_value=None):
            with self.assertRaisesRegex(pipeline.AssemblyError,
                                        "workspace_must_be_new"):
                self.invoke()
        self.assertEqual(list(self.workspace.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
