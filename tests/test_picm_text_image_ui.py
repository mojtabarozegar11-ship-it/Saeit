"""PICM text-to-image UI contract and private Django queue tests."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, TestCase
from core import picm_views as picm

ROOT = Path(__file__).resolve().parents[1]


class PICMTextImageOwnerTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        env = patch.dict(os.environ, {"PICM_STORAGE_DIR": self.temp.name})
        env.start()
        self.addCleanup(env.stop)
        (Path(self.temp.name) / ".owner-user-id").write_text("42\n", encoding="ascii")
        (Path(self.temp.name) / "worker-token").write_text("X" * 64 + "\n", encoding="ascii")
        self.rf = RequestFactory()
        self.owner = SimpleNamespace(pk=42, is_active=True, is_authenticated=True)

    def test_owner_gets_real_ai_mode_not_fake_8k_or_video_claims(self):
        req = self.rf.get("/picm/workspace/")
        req.user = self.owner
        response = picm.picm_workbench(req)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn('id="mode-text_image"', html)
        self.assertIn('id="text-image-options"', html)
        self.assertIn('id="picm-ai-style"', html)
        self.assertIn('id="picm-ai-steps"', html)
        self.assertIn('id="picm-text-resume"', html)
        self.assertIn('fetch("/picm/api/submit/"', html)
        self.assertIn('"/picm/api/status/"+id+"/"', html)
        self.assertIn('"/picm/image/"+id+"/"', html)
        self.assertIn("۲۵۶×۲۵۶", html)
        self.assertIn("GPU", html)
        self.assertIn("X-CSRFToken", html)
        self.assertNotIn('src="https://', html)

    def test_another_signed_in_user_cannot_open_workspace(self):
        req = self.rf.get("/picm/workspace/")
        req.user = SimpleNamespace(pk=43, is_active=True, is_authenticated=True)
        self.assertEqual(picm.picm_workbench(req).status_code, 403)

    def test_real_private_text_image_api_accepts_only_owner(self):
        body = {"prompt": "Photorealistic green wheat at sunrise", "style": "natural", "steps": 1}
        req = self.rf.post("/picm/api/submit/", data=json.dumps(body),
                           content_type="application/json")
        req.user = self.owner
        response = picm.picm_submit(req)
        self.assertEqual(response.status_code, 202)
        result = json.loads(response.content)
        self.assertEqual(result["state"], "queued")
        ident = result["id"]
        self.assertRegex(ident, r"^[a-f0-9]{32}$")
        with picm.locked() as root:
            job = picm.load_job(root, ident)
            self.assertEqual(job["user_id"], 42)
            self.assertEqual(job["steps"], 1)
            self.assertIn("Photorealistic green wheat at sunrise", job["prompt"])
        other = self.rf.get("/picm/api/status/" + ident + "/")
        other.user = SimpleNamespace(pk=43, is_active=True, is_authenticated=True)
        self.assertEqual(picm.picm_status(other, ident).status_code, 403)
        unsigned = self.rf.get("/picm/image/" + ident + "/")
        unsigned.user = SimpleNamespace(pk=88, is_active=True, is_authenticated=True)
        from django.http import Http404
        with self.assertRaises(Http404):
            picm.picm_image(unsigned, ident)

    def test_ui_always_discloses_cpu_resolution_and_non_generative_video(self):
        html=(ROOT / "templates/picm/index.html").read_text(encoding="utf-8")
        text=(ROOT / "templates/picm/text_image.js").read_text(encoding="utf-8")
        self.assertIn("۲۵۶", html)
        self.assertIn("حرکت سادهٔ عکس", html)
        self.assertIn("فیلم واقعی تولید نمی‌شود", html)
        self.assertIn("CPU", text)
        self.assertIn("authenticatedUrl", text)
        self.assertIn('photo.required=!selected', text)
        self.assertIn('event.stopImmediatePropagation()', text)
        self.assertIn('blob.type!=="image/png"', text)
