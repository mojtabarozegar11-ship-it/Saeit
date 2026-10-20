"""Static checks for optional external PICM free-GPU notebook.

No GPU, model, user image or external service is invoked by this test.
"""
import ast
import json
from pathlib import Path
import unittest

FILE=Path(__file__).resolve().parents[1]/"ops/picm-gpu/PICM_Free_GPU_Video_and_AI_Upscale.ipynb"

class NotebookChecks(unittest.TestCase):
    def setUp(self):
        self.nb=json.loads(FILE.read_text(encoding="utf-8"))
        self.code=[ "".join(c["source"]) for c in self.nb["cells"] if c["cell_type"]=="code" ]
        self.prose="\n".join("".join(c["source"]) for c in self.nb["cells"] if c["cell_type"]=="markdown")
    def test_valid_notebook_contract(self):
        self.assertEqual(self.nb["nbformat"],4)
        self.assertGreaterEqual(len(self.code),7)
        for code in self.code:
            for line in code.splitlines():
                if line.lstrip().startswith(("%","!")):
                    continue
            compiled="\n".join(l for l in code.splitlines() if not l.lstrip().startswith(("%","!")))
            ast.parse(compiled)
    def test_video_is_real_generation_not_slideshow(self):
        joined="\n".join(self.code)
        self.assertIn("LTXImageToVideoPipeline",joined)
        self.assertIn("image=frame",joined)
        self.assertIn("num_frames=FRAMES",joined)
        self.assertIn("export_to_video(",joined)
        self.assertIn("torch.cuda.is_available()",joined)
        self.assertIn("FRAMES = 49",joined)
    def test_upscale_is_transparent_not_native_8k(self):
        joined="\n".join(self.code)
        self.assertIn("RealESRGAN_x4plus",joined)
        self.assertIn('"--tile","128"',joined)
        self.assertIn("7680",joined)
        self.assertIn("Image.Resampling.LANCZOS",joined)
        self.assertIn("not native 8K",self.prose.lower())
    def test_no_private_inputs_published_into_public_github(self):
        joined="\n".join(self.code)
        self.assertIn("files.upload()",joined)
        self.assertIn("files.download(",joined)
        self.assertNotIn("mojplaywin.com/picm/api",joined)
        self.assertNotIn("actions/upload-artifact",joined)
        self.assertNotIn("stripe",joined.lower())
        self.assertIn("not guaranteed",self.prose.lower())

if __name__=="__main__":
    unittest.main()
