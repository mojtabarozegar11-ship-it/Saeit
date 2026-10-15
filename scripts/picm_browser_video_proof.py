#!/usr/bin/env python3
"""End-to-end browser video proof using Chromium, no external API or user files.

Loads the actual PICM recorder JS into an isolated DOM with a synthetic PNG,
generates a ten-second clip, inspects MP4/WebM file bytes and validates that
the download button exists. Requires Python playwright + installed Chromium.
"""
import asyncio
import binascii
from pathlib import Path
import struct
import zlib

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "templates/picm/free_motion.js"


def png_fixture():
    def chunk(label, raw):
        return (struct.pack(">I", len(raw)) + label + raw
                + struct.pack(">I", binascii.crc32(label + raw) & 0xffffffff))
    width = height = 512
    row = b"\x00" + b"\x40\x60\x90" * width
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(row * height))
            + chunk(b"IEND", b""))


HTML = """
<html><head><title>PICM Test</title></head><body>
<div id="preview">EMPTY</div><p id="status">READY</p>
<div id="capability-notice"></div>
<div id="video-options">
<select id="video-duration"><option value="10" selected>10 seconds</option>
<option value="30">30 seconds</option><option value="60">60 seconds</option></select>
<select id="video-ratio"><option value="wide" selected>Landscape</option></select>
</div>
<div id="photo-options"></div>
<form id="renderform">
<input type="hidden" id="mode" value="image_video">
<input type="file" id="photo" required>
<textarea id="prompt"></textarea>
<label for="prompt">Caption</label>
<button id="submit" type="submit">Generate</button>
<button id="video-cancel" hidden type="button">Cancel</button>
</form>
</body></html>
"""


async def test():
    assert SCRIPT.is_file()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            channel="chrome",
            headless=True,
            args=["--no-sandbox", "--autoplay-policy=no-user-gesture-required"],
        )
        try:
            context = await browser.new_context(
                accept_downloads=True,
                viewport={"width": 1000, "height": 760},
                reduced_motion="no-preference",
            )
            page = await context.new_page()
            # The actual JavaScript must be parsed and run in the real browser.
            await page.set_content(HTML)
            await page.add_script_tag(content=SCRIPT.read_text(encoding="utf-8"))
            assert await page.locator("#prompt").evaluate("(el) => !el.required")
            await page.locator("#photo").set_input_files({
                "name": "synthetic.png",
                "mimeType": "image/png",
                "buffer": png_fixture(),
            })
            await page.locator("#submit").click()
            await page.locator('a[download^="picm-free-motion-"]').wait_for(
                state="attached", timeout=35000
            )
            details = await page.evaluate(
                """async () => {
                    const link=document.querySelector('a[download^="picm-free-motion-"]');
                    const result=await fetch(link.href);
                    const blob=await result.blob();
                    const start=Array.from(new Uint8Array(await blob.slice(0,16).arrayBuffer()));
                    const isMP4=String.fromCharCode(...start.slice(4,8))==="ftyp";
                    const isWebM=start[0]===26&&start[1]===69&&start[2]===223&&start[3]===163;
                    return {name:link.download,byteLength:blob.size,isMP4,isWebM,
                            status:document.getElementById("status").textContent,
                            hasVideo:!!document.querySelector("#preview video")};
                }"""
            )
            assert details["hasVideo"]
            assert details["byteLength"] >= 1024, details
            assert details["isMP4"] or details["isWebM"], details
            assert details["name"].endswith((".mp4", ".webm")), details
            assert "فایل ویدیویی" in details["status"], details
            print("PICM_BROWSER_REAL_VIDEO_OUTPUT_OK")
            print("PICM_BROWSER_VIDEO_BYTES_GT_1024")
            print("PICM_BROWSER_VIDEO_FORMAT", "MP4" if details["isMP4"] else "WEBM")
            print("PICM_BROWSER_DOWNLOAD_CONTROL_READY")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(test())
