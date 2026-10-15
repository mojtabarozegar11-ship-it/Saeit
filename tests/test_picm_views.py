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
        with self.assertRaises(Http404):
            v.picm_status(status, ident)
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
