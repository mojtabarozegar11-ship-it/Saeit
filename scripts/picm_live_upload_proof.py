#!/usr/bin/env python3
"""Bounded, credential-free live PICM photo-input acceptance proof on cPanel."""
import binascii
import json
import struct
import sys
import time
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
    created = []
    try:
        for index, mode in enumerate(("image_edit", "image_video", "upscale_8k")):
            user = SimpleNamespace(pk=-(int(time.time()) + 713000 + index),
                                   is_authenticated=True)
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
