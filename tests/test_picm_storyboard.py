"""PICM owner-only story-to-film planning tests, no GPU or paid backend."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, RequestFactory
from django.core.files.uploadedfile import SimpleUploadedFile
from core import picm_views as views
from core.picm_storyboard import plan_story


class StoryboardPlannerTests(TestCase):
    def test_morning_routine_has_identity_and_exact_60_seconds(self):
        plan = plan_story("از خواب بیدار شود، صبحانه بخورد، لباس بپوشد و به سر کار برود", 60, "wide")
        self.assertEqual(plan["duration"], 60)
        self.assertEqual(len(plan["scenes"]), 10)
        self.assertEqual(sum(shot["duration"] for shot in plan["scenes"]), 60)
        self.assertEqual(plan["scenes"][0]["start"], 0)
        self.assertEqual(plan["scenes"][-1]["end"], 60)
        self.assertIn("خواب", plan["scenes"][0]["action"])
        self.assertIn("کار", plan["scenes"][-1]["action"])
        self.assertTrue(all(s["identity"] == "same_reference_person" for s in plan["scenes"]))
        self.assertFalse(plan["actual_video_ready"])
        self.assertEqual(plan["render_state"], "awaiting_gpu")

    def test_all_4_durations_make_timed_clips(self):
        for duration in (5, 10, 30, 60):
            plan = plan_story("یک شخصیت به باغ می‌رود سپس وارد کلاس می‌شود و بازمی‌گردد", duration, "vertical")
            self.assertEqual(sum(s["duration"] for s in plan["scenes"]), duration)
            self.assertEqual(plan["scenes"][-1]["end"], duration)
            self.assertEqual(plan["ratio"], "9:16")

    def test_invalid_requests_not_accepted(self):
        for data in (("هی", 60, "wide"), ("داستان چند صحنه", 61, "wide"),
                     ("داستان چند صحنه", 60, "invalid"), ("داستان چند صحنه", "60", "wide")):
            with self.assertRaises(ValueError):
                plan_story(*data)


class PrivateStoryStageTests(TestCase):
    def setUp(self):
        self.store = tempfile.TemporaryDirectory()
        self.addCleanup(self.store.cleanup)
        env = patch.dict(os.environ, {"PICM_STORAGE_DIR": self.store.name})
        env.start()
        self.addCleanup(env.stop)
        (Path(self.store.name) / ".owner-user-id").write_text("101\n", encoding="ascii")
        self.rf = RequestFactory()

    @staticmethod
    def image():
        raw = (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" +
               (512).to_bytes(4, "big") + (512).to_bytes(4, "big") +
               b"\x08\x02\x00\x00\x00" + b"8" * 400)
        return SimpleUploadedFile("reference.png", raw, content_type="image/png")

    def send(self, duration="60", user=101):
        req = self.rf.post("/picm/api/reference/", data={
            "photo": self.image(), "mode": "story_video",
            "duration": duration, "ratio": "wide",
            "prompt": "صبح از خواب بیدار شود، صبحانه بخورد، لباس بپوشد و سر کار برود"})
        req.user = SimpleNamespace(pk=user, is_authenticated=True, is_active=True)
        return views.picm_reference_stage(req)

    def test_single_owner_story_status_and_private_files(self):
        response = self.send()
        self.assertEqual(response.status_code, 202)
        data = json.loads(response.content)
        self.assertEqual(data["state"], "staged_awaiting_gpu")
        self.assertEqual(len(data["storyboard"]["scenes"]), 10)
        self.assertFalse(data["storyboard"]["actual_video_ready"])
        identifier = data["id"]
        private_file = Path(self.store.name) / (identifier + ".input")
        self.assertTrue(private_file.exists())
        self.assertEqual(private_file.stat().st_mode & 0o777, 0o600)
        self.assertFalse((Path(self.store.name) / (identifier + ".mp4")).exists())
        req = self.rf.get("/picm/api/reference/" + identifier + "/")
        req.user = SimpleNamespace(pk=101, is_authenticated=True, is_active=True)
        self.assertEqual(json.loads(views.picm_reference_status(req, identifier).content)["storyboard"]["duration"],60)
        req.user = SimpleNamespace(pk=102, is_authenticated=True, is_active=True)
        from django.http import Http404
        with self.assertRaises(Http404):
            views.picm_reference_status(req, identifier)

    def test_no_fixed_count_limit_for_personal_story_preparations(self):
        for _ in range(5):
            self.assertEqual(self.send().status_code, 202)

    def test_invalid_duration_and_nonowner_rejected(self):
        self.assertEqual(self.send(duration="15").status_code, 400)
        self.assertEqual(self.send(user=999).status_code, 403)
