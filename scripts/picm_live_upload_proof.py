#!/usr/bin/env python3
"""Bounded, credential-free live PICM photo-input acceptance proof on cPanel."""
import binascii
import json
import struct
import sys
import zlib
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, "/home/zomorod2/Saeit-staging")
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.test import RequestFactory
from django.core.files.uploadedfile import SimpleUploadedFile
from core.picm_views import picm_reference_stage, picm_reference_status, locked
from core.picm_access import owner_id


def make_png():
    def chunk(name, data):
        crc = binascii.crc32(name + data) & 0xffffffff
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", crc)
    width, height = 512, 512
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    rows = (b"\x00" + b"\x00\x11\x22" * width) * height
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(rows))
            + chunk(b"IEND", b""))


def main():
    image = make_png()
    factory = RequestFactory()
    bound_owner = owner_id()
    if bound_owner is None:
        raise RuntimeError("PICM_OWNER_BINDING_MISSING")
    # Use the existing bound owner ID, never a fake user. The authorization
    # gate must remain intact; synthetic files are deleted in the finally block.
    owner = SimpleNamespace(pk=int(bound_owner), is_authenticated=True, is_active=True)
    created = []
    try:
        for index, mode in enumerate(("image_edit", "image_video", "upscale_8k")):
            user = owner
            prompt = "" if mode == "upscale_8k" else "Synthetic reference upload test"
            request = factory.post("/picm/api/reference/", data={
                "mode": mode, "prompt": prompt,
                "photo": SimpleUploadedFile("synthetic.png", image,
                                             content_type="image/png")})
            request.user = user
            response = picm_reference_stage(request)
            assert response.status_code == 202, (mode, response.status_code)
            data = json.loads(response.content)
            assert data["state"] == "staged_awaiting_gpu" and data["mode"] == mode
            ident = data["id"]
            created.append(ident)
            with locked() as root:
                path = root / (ident + ".input")
                assert path.read_bytes() == image
                assert path.stat().st_mode & 0o777 == 0o600
                assert not (root / (ident + ".json")).exists()
            probe = factory.get("/picm/api/reference/" + ident + "/")
            probe.user = user
            assert picm_reference_status(probe, ident).status_code == 200
            print("PICM_LIVE_PRIVATE_STAGE_OK_" + mode.upper())
            # Keep one synthetic reference staged at a time. The private owner
            # may already have real photos staged; never delete or count those
            # as test artifacts, and avoid exhausting the three-photo limit.
            with locked() as root:
                for suffix in (".input", ".stage.json"):
                    item = root / (ident + suffix)
                    if item.is_file() and not item.is_symlink():
                        item.unlink()
            created.remove(ident)
        print("PICM_ALL_THREE_PHOTO_MODES_SITE_API_PROVEN")
    finally:
        with locked() as root:
            for ident in created:
                for suffix in (".input", ".stage.json"):
                    path = root / (ident + suffix)
                    if path.is_file() and not path.is_symlink():
                        path.unlink()
        print("PICM_SYNTHETIC_REFERENCE_FILES_REMOVED")


if __name__ == "__main__":
    main()
