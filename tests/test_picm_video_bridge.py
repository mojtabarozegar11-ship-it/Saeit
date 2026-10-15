"""Offline Django tests for PICM private GPU transfer and protected MP4 return.

A small synthetic MP4-header fixture exercises transport authorization only;
it is NOT evidence of AI video generation or visual quality.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.test import RequestFactory, TestCase

from core import picm_video_bridge as b
from core import picm_views as v


class PICMPrivateMovieBridgeTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(os.environ, {"PICM_STORAGE_DIR": self.tmp.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.root = Path(self.tmp.name)
        self.root.chmod(0o700)
        (self.root / ".owner-user-id").write_text("101\n", encoding="ascii")
        token = self.root / "gpu-worker-token"
        token.write_text("Z" * 64)
        token.chmod(0o600)
        self.rf = RequestFactory()
        self.owner = SimpleNamespace(pk=101, is_authenticated=True, is_active=True)
        self.other = SimpleNamespace(pk=102, is_authenticated=True, is_active=True)

    def _stage(self):
        # Minimal bounded image accepted by PICM staging (no external image).
        png = (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR"
               + (512).to_bytes(4, "big") + (512).to_bytes(4, "big")
               + b"\x08\x02\x00\x00\x00" + b"0" * 200)
        req = self.rf.post("/picm/api/reference/", data={
            "mode": "story_video",
            "prompt": "صبح از خواب بیدار شود و صبحانه بخورد و سر کار برود",
            "duration": "5", "ratio": "wide",
            "photo": SimpleUploadedFile("photo.png", png, content_type="image/png"),
        })
        req.user = self.owner
        res = v.picm_reference_stage(req)
        self.assertEqual(res.status_code, 202)
        return json.loads(res.content)["id"]

    def _worker(self, function, route, ident=None, *, method="get",
                lease=None, data=None, headers=None, authorized=True,
                content_type=None):
        fields = dict(headers or {})
        if authorized:
            fields["HTTP_AUTHORIZATION"] = "Bearer " + "Z" * 64
        if lease:
            fields["HTTP_X_PICM_VIDEO_LEASE"] = lease
        if method == "get":
            req = self.rf.get(route, **fields)
        else:
            req = self.rf.post(route, data=(data if data is not None else b""),
                               content_type=content_type or "application/octet-stream",
                               **fields)
        return function(req, ident) if ident is not None else function(req)

    def _claim(self):
        response = self._worker(b.video_worker_next, "/picm/video/worker/next/")
        self.assertEqual(response.status_code, 200)
        return json.loads(response.content)

    def test_missing_gpu_token_is_fail_closed_and_no_job_claim(self):
        ident = self._stage()
        res = self._worker(b.video_worker_next, "/picm/video/worker/next/", authorized=False)
        self.assertEqual(res.status_code, 403)
        self.assertFalse((self.root / (ident + ".video.json")).exists())
        (self.root / "gpu-worker-token").chmod(0o644)
        self.assertEqual(
            self._worker(b.video_worker_next, "/picm/video/worker/next/").status_code, 403)

    def test_valid_one_owner_only_job_and_lease_protected_photo(self):
        ident = self._stage()
        result = self._claim()
        self.assertEqual(result["id"], ident)
        self.assertEqual(result["duration"], 5)
        self.assertEqual(self._worker(
            b.video_worker_next, "/picm/video/worker/next/").status_code, 204)
        path = "/picm/video/worker/"
        self.assertEqual(self._worker(b.video_worker_metadata,
            path + "metadata/" + ident + "/", ident, lease="f" * 32).status_code, 409)
        self.assertEqual(self._worker(b.video_worker_reference,
            path + "reference/" + ident + "/", ident, authorized=False,
            lease=result["lease"]).status_code, 403)
        metadata = self._worker(b.video_worker_metadata,
            path + "metadata/" + ident + "/", ident, lease=result["lease"])
        self.assertEqual(json.loads(metadata.content)["mode"], "story_video")
        photo = self._worker(b.video_worker_reference,
            path + "reference/" + ident + "/", ident, lease=result["lease"])
        self.assertEqual(photo.status_code, 200)
        self.assertTrue(b"".join(photo.streaming_content).startswith(b"\x89PNG"))
        photo.close()

    def _synthetic_mp4(self):
        # Pure transport fixture, NOT a valid AI-generated film.
        return b"\x00\x00\x00\x18ftypisom" + b"x" * 20 + b"moov" + b"y" * 4200

    def _upload(self, ident, lease, content, *, reported_sha=None):
        digest = reported_sha or hashlib.sha256(content).hexdigest()
        offset = 0
        while offset < len(content):
            chunk = content[offset:offset + 1024]
            res = self._worker(b.video_worker_chunk,
                "/picm/video/worker/chunk/" + ident + "/", ident,
                method="post", lease=lease, data=chunk,
                headers={"HTTP_X_PICM_OFFSET": str(offset),
                         "HTTP_X_PICM_TOTAL": str(len(content)),
                         "HTTP_X_PICM_SHA256": digest})
            self.assertEqual(res.status_code, 200)
            offset = json.loads(res.content)["offset"]
        return digest

    def _finish(self, ident, lease, size, digest):
        payload = {"state": "real_mp4_rendered_and_ffprobed",
                   "job_id": ident, "bytes": size,
                   "duration": 5, "sha256": digest}
        return self._worker(b.video_worker_finish,
            "/picm/video/worker/finish/" + ident + "/", ident,
            method="post", lease=lease, data=json.dumps(payload),
            content_type="application/json")

    def test_sha_chunked_upload_and_owner_only_mp4_download(self):
        ident = self._stage()
        lease = self._claim()["lease"]
        content = self._synthetic_mp4()
        digest = self._upload(ident, lease, content)
        self.assertEqual(self._finish(ident, lease, len(content), digest).status_code, 200)
        saved = self.root / (ident + ".mp4")
        self.assertEqual(saved.read_bytes(), content)
        self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.root / (ident + ".mp4.part")).exists())
        self.assertEqual(self._finish(ident, lease, len(content), digest).status_code, 409)
        request = self.rf.get("/picm/video/status/" + ident + "/")
        request.user = self.owner
        state = b.video_owner_status(request, ident)
        self.assertEqual(json.loads(state.content)["state"], "done")
        request.user = self.other
        with self.assertRaises(Http404):
            b.video_owner_status(request, ident)
        with self.assertRaises(Http404):
            b.video_owner_download(request, ident)
        request.user = self.owner
        response = b.video_owner_download(request, ident)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), content)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        response.close()

    def test_duplicate_chunk_bad_offset_and_false_sha_rejected(self):
        ident = self._stage()
        lease = self._claim()["lease"]
        content = self._synthetic_mp4()
        hash_value = hashlib.sha256(content).hexdigest()
        headers={"HTTP_X_PICM_OFFSET": "1", "HTTP_X_PICM_TOTAL": str(len(content)),
                 "HTTP_X_PICM_SHA256": hash_value}
        response = self._worker(b.video_worker_chunk,
            "/picm/video/worker/chunk/" + ident + "/", ident, method="post",
            lease=lease, data=content[:1000], headers=headers)
        self.assertEqual(response.status_code, 409)
        self.assertFalse((self.root / (ident + ".mp4.part")).exists())
        fake_digest = "a" * 64
        self._upload(ident, lease, content, reported_sha=fake_digest)
        self.assertEqual(self._finish(ident, lease, len(content), fake_digest).status_code, 422)
        self.assertFalse((self.root / (ident + ".mp4")).exists())

    def test_expired_movie_download_and_wrong_duration_are_rejected(self):
        ident = self._stage()
        lease = self._claim()["lease"]
        content = self._synthetic_mp4()
        digest = self._upload(ident, lease, content)
        receipt = {"state": "real_mp4_rendered_and_ffprobed", "job_id": ident,
                   "bytes": len(content), "sha256": digest, "duration": 60}
        res = self._worker(b.video_worker_finish, "/picm/video/worker/finish/" + ident + "/",
            ident, method="post", lease=lease, data=json.dumps(receipt),
            content_type="application/json")
        self.assertEqual(res.status_code, 410)
        self.assertFalse((self.root / (ident + ".mp4")).exists())

    def test_video_bridge_does_not_expose_unclaimed_story(self):
        ident = self._stage()
        req = self.rf.get("/picm/video/status/" + ident + "/")
        req.user = self.owner
        self.assertEqual(
            json.loads(b.video_owner_status(req, ident).content)["state"],
            "staged_awaiting_gpu")
        self.assertEqual(self._worker(b.video_worker_reference,
            "/picm/video/worker/reference/" + ident + "/", ident,
            lease="a" * 32).status_code, 409)
