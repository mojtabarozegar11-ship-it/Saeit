#!/usr/bin/env python3
"""Independent actual Chromium execution of the factory F14 browser-game pilot."""
import argparse
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading

def check(source, outfile):
    from playwright.sync_api import sync_playwright
    if source.is_symlink() or not all((source / f).is_file() for f in
                                     ("mini_game.html", "game.js", "browser_game.zip")):
        raise RuntimeError("F14_BROWSER_ORIGINAL_ARTIFACT_MISSING")
    class LocalOnly(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(source), **kwargs)
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), LocalOnly)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    tested = []
    try:
        with sync_playwright() as engine:
            browser = engine.chromium.launch(headless=True)
            try:
                for label, width, height in (("desktop", 1280, 800),
                                             ("mobile", 375, 740)):
                    page = browser.new_page(viewport={"width":width, "height":height},
                                            is_mobile=(label == "mobile"),
                                            has_touch=(label == "mobile"))
                    errors = []
                    external = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.on("request", lambda req: external.append(req.url)
                            if not req.url.startswith("http://127.0.0.1:") else None)
                    page.goto("http://127.0.0.1:%d/mini_game.html" % server.server_port,
                              wait_until="load", timeout=20000)
                    page.wait_for_function("typeof tick !== 'undefined' && tick >= 5",
                                           timeout=10000)
                    original = page.evaluate("x")
                    page.locator('button[data-d="-1"]').click()
                    moved = page.evaluate("x")
                    if moved != original - 31:
                        raise RuntimeError("F14_REAL_BROWSER_MOVEMENT_BROKEN")
                    page.keyboard.press("ArrowRight")
                    if page.evaluate("x") != original:
                        raise RuntimeError("F14_REAL_KEYBOARD_MOVEMENT_BROKEN")
                    page.locator("#restart").click()
                    page.wait_for_function("x === 200 && score === 0", timeout=5000)
                    if not page.locator("#board").is_visible():
                        raise RuntimeError("F14_CANVAS_NOT_RENDERED")
                    if (not page.locator("#board").get_attribute("aria-label") or
                            page.locator("#board").get_attribute("role") != "img" or
                            page.locator("#score").get_attribute("role") != "status" or
                            page.locator("#score").get_attribute("aria-live") != "polite"):
                        raise RuntimeError("F14_ACCESSIBILITY_REGRESSION")
                    if errors or external:
                        raise RuntimeError("F14_BROWSER_ERRORS_OR_EXTERNAL_NETWORK")
                    tested.append(label)
                    page.close()
                version=browser.version
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
    result = {
        "schema":"saeit.factory.f14-headless-chromium-proof.v1",
        "family":"F14", "actual_chromium_executed":True,
        "real_interactive_movement_tested":True,
        "keyboard_and_restart_tested":True,
        "responsive_viewports_tested":tested, "chromium_version":version,
        "source_sha256":{
            k:hashlib.sha256((source/k).read_bytes()).hexdigest()
            for k in ("mini_game.html","game.js","browser_game.zip")},
        "external_network_requests":0, "uncaught_js_errors":0,
        "physical_mobile_device_tested":False,
        "independent_player_novelty_review":False,
        "quality_1000_certified":False, "public_release":False
    }
    outfile.parent.mkdir(parents=True, exist_ok=True)
    outfile.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf8")
    print("F14_REAL_CHROMIUM_PROOF="+json.dumps(
        {"viewports":tested,"movement":True,"keyboard":True,"restart":True,
         "commercial_approval":False},sort_keys=True))

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True)
    p.add_argument("--proof",required=True)
    a=p.parse_args()
    check(Path(a.source),Path(a.proof))
