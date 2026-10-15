"""Security and real request/worker handoff tests for private PICM demo."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, TestCase
from django.http import Http404
from core import picm_views as v

PNG = (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" +
       (256).to_bytes(4, "big") + (256).to_bytes(4, "big") + b"\x08\x02\x00\x00\x00" +
       b"0" * 1100)


class PICMTest(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {"PICM_STORAGE_DIR": self.temp.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.rf = RequestFactory()
        (Path(self.temp.name) / "worker-token").write_text("X" * 64 + "\n")
        (Path(self.temp.name) / ".owner-user-id").write_text("42\n", encoding="ascii")

    def user(self, pk=42, authenticated=True):
        return SimpleNamespace(pk=pk, is_authenticated=authenticated)

    def post(self, payload, user=None):
        req = self.rf.post("/picm/api/submit/", data=json.dumps(payload),
                           content_type="application/json")
        req.user = user if user is not None else self.user()
        return v.picm_submit(req)

    def prepare(self):
        res = self.post({"prompt": "A botanical garden in sunlight",
                         "style": "cinematic", "steps": 2})
        self.assertEqual(res.status_code, 202)
        return json.loads(res.content)["id"]

    def claim(self, token=True):
        headers = {"HTTP_AUTHORIZATION": "Bearer " + "X" * 64} if token else {}
        req = self.rf.get("/picm/worker/next/", **headers)
        return v.picm_worker_next(req)

    def test_other_authenticated_user_cannot_submit_or_use_result(self):
        other = self.user(pk=700, authenticated=True)
        result = self.post({"prompt": "Landscapes with rivers", "style": "natural", "steps": 2}, other)
        self.assertEqual(result.status_code, 403)
        # Even if the user id is valid, missing binding denies all access.
        (Path(self.temp.name)/".owner-user-id").unlink()
        self.assertEqual(self.post({"prompt":"Sunlit garden", "style":"natural", "steps":1}).status_code,403)

    def test_anonymous_cannot_submit(self):
        res = self.post({"prompt": "A botanical garden", "style": "natural",
                         "steps": 1}, self.user(authenticated=False))
        self.assertEqual(res.status_code, 401)

    def test_input_is_bounded_and_rejects_commands(self):
        for payload in (
            {"prompt": "A", "style": "cinematic", "steps": 2},
            {"prompt": "A garden", "style": "bad", "steps": 2},
            {"prompt": "A garden", "style": "natural", "steps": 99},
            {"prompt": "A garden", "style": "natural", "steps": "2"},
        ):
            self.assertEqual(self.post(payload).status_code, 400)

    def test_worker_requires_private_token(self):
        ident = self.prepare()
        self.assertEqual(self.claim(token=False).status_code, 403)
        claim = self.claim()
        self.assertEqual(claim.status_code, 200)
        job = json.loads(claim.content)
        self.assertEqual(job["id"], ident)
        self.assertEqual(job["steps"], 2)
        self.assertEqual(self.claim().status_code, 204)
        self.assertNotIn("user_id", claim.content.decode("utf-8"))

    def test_user_only_sees_their_image(self):
        ident = self.prepare()
        job = json.loads(self.claim().content)
        request = self.rf.post("/picm/worker/finish/" + ident + "/", data=PNG,
                               content_type="image/png",
                               HTTP_AUTHORIZATION="Bearer " + "X" * 64,
                               HTTP_X_PICM_LEASE=job["lease"])
        self.assertEqual(v.picm_worker_finish(request, ident).status_code, 200)
        status = self.rf.get("/picm/api/status/" + ident + "/")
        status.user = self.user(42)
        self.assertEqual(json.loads(v.picm_status(status, ident).content)["state"], "done")
        status.user = self.user(99)
        self.assertEqual(v.picm_status(status, ident).status_code, 403)
        image_req = self.rf.get("/picm/image/" + ident + "/")
        image_req.user = self.user(42)
        result = v.picm_image(image_req, ident)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(b"".join(result.streaming_content), PNG)
        result.close()

    def test_invalid_png_does_not_complete(self):
        ident = self.prepare()
        job = json.loads(self.claim().content)
        req = self.rf.post("/picm/worker/finish/" + ident + "/", data=b"no image",
                           content_type="image/png",
                           HTTP_AUTHORIZATION="Bearer " + "X" * 64,
                           HTTP_X_PICM_LEASE=job["lease"])
        self.assertEqual(v.picm_worker_finish(req, ident).status_code, 422)
        state_req = self.rf.get("/picm/api/status/" + ident + "/")
        state_req.user = self.user()
        self.assertEqual(json.loads(v.picm_status(state_req, ident).content)["state"], "running")

    def test_quota_enforced(self):
        for i in range(v.DAILY_QUOTA):
            self.assertEqual(self.post({"prompt": f"Botanical garden image {i}",
                                        "style": "cinematic", "steps": 1}).status_code, 202)
        self.assertEqual(self.post({"prompt": "One more landscape",
                                    "style": "cinematic", "steps": 1}).status_code, 429)



class PICMPhotoReferenceTests(TestCase):
    """Actual multipart upload prep for modes 2, 4 and 5 only."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {"PICM_STORAGE_DIR": self.temp.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.rf = RequestFactory()
        (Path(self.temp.name) / ".owner-user-id").write_text("101\\n".replace("\\\\n", "\\n"), encoding="ascii")

    def photo(self, width=512, height=512):
        from django.core.files.uploadedfile import SimpleUploadedFile
        data = (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR"
                + width.to_bytes(4, "big") + height.to_bytes(4, "big")
                + b"\x08\x02\x00\x00\x00" + b"0123456789" * 32)
        return SimpleUploadedFile("private.png", data, content_type="image/png")

    def submit(self, mode="image_edit", prompt="Improve contrast and light", user=101, include_photo=True):
        payload = {"mode": mode, "prompt": prompt}
        if include_photo:
            payload["photo"] = self.photo()
        req = self.rf.post("/picm/api/reference/", data=payload)
        req.user = SimpleNamespace(pk=user, is_authenticated=user is not None)
        return v.picm_reference_stage(req)

    def test_all_three_modes_stage_privately_without_claiming_gpu_output(self):
        for mode in ("image_edit", "image_video", "upscale_8k"):
            result = self.submit(mode, "" if mode=="upscale_8k" else "Improve detail")
            self.assertEqual(result.status_code, 202)
            data=json.loads(result.content)
            self.assertEqual(data["state"], "staged_awaiting_gpu")
            self.assertEqual(data["mode"],mode)
            self.assertEqual((data["width"],data["height"]),(512,512))
            ident=data["id"]
            raw_path=Path(self.temp.name)/(ident+".input")
            self.assertTrue(raw_path.is_file())
            self.assertEqual(raw_path.stat().st_mode & 0o777,0o600)
            self.assertFalse((Path(self.temp.name)/(ident+".json")).exists())
            req=self.rf.get("/picm/api/reference/"+ident+"/")
            req.user=SimpleNamespace(pk=101,is_authenticated=True)
            self.assertEqual(json.loads(v.picm_reference_status(req,ident).content)["state"],"staged_awaiting_gpu")
            req.user=SimpleNamespace(pk=202,is_authenticated=True)
            with self.assertRaises(Http404):
                v.picm_reference_status(req,ident)

    def test_old_modes_and_missing_photo_not_accepted(self):
        for mode in ("text_image","text_video","anything"):
            response=self.submit(mode)
            self.assertEqual(response.status_code,400)
        self.assertEqual(self.submit(include_photo=False).status_code,400)
        self.assertEqual(self.submit("image_edit",prompt="").status_code,400)
        self.assertEqual(self.submit("upscale_8k",prompt="No prompt").status_code,400)
        anonymous=self.submit(user=None)
        self.assertEqual(anonymous.status_code,401)

    def test_invalid_oversized_dimensions_and_quota(self):
        self.assertEqual(self.submit(mode="image_edit").status_code,202)
        self.assertEqual(self.submit(mode="image_video").status_code,202)
        self.assertEqual(self.submit(mode="upscale_8k",prompt="").status_code,202)
        self.assertEqual(self.submit().status_code,429)
        oversized=self.rf.post("/picm/api/reference/", data={
            "mode":"image_edit","prompt":"Make realistic","photo":self.photo(8193,1024)})
        oversized.user=SimpleNamespace(pk=802,is_authenticated=True)
        self.assertEqual(v.picm_reference_stage(oversized).status_code,422)

    def test_rejects_file_not_matching_image_header(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        req=self.rf.post("/picm/api/reference/", data={"mode":"image_edit",
            "prompt":"Make it cinematic",
            "photo": SimpleUploadedFile("fake.jpg",b"<script>wrong data</script>"*40,
                                        content_type="image/jpeg")})
        req.user=SimpleNamespace(pk=101,is_authenticated=True)
        self.assertEqual(v.picm_reference_stage(req).status_code,415)
