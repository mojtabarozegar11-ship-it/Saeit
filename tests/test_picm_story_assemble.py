"""PICM GPU compositor tests: only genuine validated scene clips produce MP4."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "ops" / "picm-gpu" / "story_assemble.py"
spec = importlib.util.spec_from_file_location("picm_gpu_assembly", MODULE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class StoryAssemblerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.clips = self.root / "clips"
        self.clips.mkdir()
        self.out = self.root / "output"
        self.out.mkdir()
        self.plan = {
            "duration": 5, "ratio": "16:9",
            "scenes": [{"shot": 1, "start": 0, "end": 5, "duration": 5}],
            "actual_video_ready": False, "render_state": "awaiting_gpu",
        }
        self.json_path = self.root / "story.stage.json"
        self.json_path.write_text(json.dumps({"storyboard": self.plan}))

    def test_private_plan_loads_without_claiming_video(self):
        plan = m.load_plan(self.json_path)
        self.assertEqual(plan["duration"], 5)
        self.assertFalse(plan["actual_video_ready"])

    def test_reject_corrupt_timeline_or_unusual_length(self):
        self.plan["scenes"][0]["end"] = 7
        self.json_path.write_text(json.dumps({"storyboard": self.plan}))
        with self.assertRaisesRegex(m.AssemblyError, "inconsistent_scene_timing"):
            m.load_plan(self.json_path)
        self.plan["scenes"][0]["end"] = 5
        self.plan["duration"] = 99
        self.json_path.write_text(json.dumps({"storyboard": self.plan}))
        with self.assertRaisesRegex(m.AssemblyError, "invalid_story_duration"):
            m.load_plan(self.json_path)

    def test_refuses_to_fabricate_video_if_real_scene_missing(self):
        with patch.object(m, "_verify_tools"):
            with self.assertRaisesRegex(m.AssemblyError, "missing_real_ai_clip"):
                m.assemble(self.plan, self.clips, self.out / "story.mp4")
        self.assertFalse((self.out / "story.mp4").exists())

    def test_rejects_symlink_scene_for_private_storage(self):
        original = self.root / "external.mp4"
        original.write_bytes(b"fake")
        (self.clips / "shot_01.mp4").symlink_to(original)
        with patch.object(m, "_verify_tools"):
            with self.assertRaisesRegex(m.AssemblyError, "missing_real_ai_clip"):
                m.assemble(self.plan, self.clips, self.out / "story.mp4")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                         "ffmpeg is not available on CI")
    def test_real_video_clip_is_assembled_and_probed(self):
        sample = self.clips / "shot_01.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc2=size=256x144:rate=8",
            "-t", "5.05", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-y", str(sample)], check=True, timeout=45)
        result = m.assemble(self.plan, self.clips, self.out / "story.mp4")
        self.assertTrue(result.is_file())
        self.assertGreater(result.stat().st_size, 3000)
        self.assertLess(abs(m.video_duration(result) - 5), 0.5)
        self.assertEqual(result.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
