#!/usr/bin/env python3
"""Standalone browser smoke for isolated MojPlayWin Arcade Lab build."""
import http.server
import socketserver
import threading
import sys
from pathlib import Path
from functools import partial
from playwright.sync_api import sync_playwright

root = Path(sys.argv[1]).resolve()
assert (root / "circuit-courier" / "engine.js").is_file()
assert len(list(root.glob("guides/[0-9][0-9]/index.html"))) == 50

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        return

with socketserver.TCPServer(("127.0.0.1", 0), partial(Quiet, directory=str(root))) as server:
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:" + str(server.server_address[1])
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            for width, height in ((390, 844), (1365, 900)):
                context = browser.new_context(viewport={"width": width, "height": height}, is_mobile=(width == 390), has_touch=(width == 390))
                try:
                    page = context.new_page()
                    faults = []
                    page.on("pageerror", lambda exc: faults.append(str(exc)))
                    for path, heading in (
                        ("/index.html", "Play. Balance. Test."),
                        ("/circuit-courier/index.html", "Circuit Courier"),
                        ("/economy-simulator/index.html", "Game Economy Simulator"),
                        ("/qa-matrix/index.html", "Game QA Matrix"),
                        ("/guides/index.html", "50")
                    ):
                        response = page.goto(url + path, wait_until="load")
                        assert response and response.status == 200, (path, response.status if response else None)
                        assert heading.casefold() in page.locator("body").inner_text().casefold(), path
                    page.goto(url + "/circuit-courier/index.html", wait_until="load")
                    assert page.locator("#board").locator("*").count() >= 49
                    assert page.locator("#level").inner_text().startswith("1/")
                    page.locator("#hint").click()
                    page.locator("#right").click()
                    page.locator("#undo").click()
                    page.reload(wait_until="load")
                    assert page.locator("#board").locator("*").count() >= 49
                    page.goto(url + "/economy-simulator/index.html", wait_until="load")
                    assert page.locator("#rows tr").count() > 0
                    page.locator("#calculate").click()
                    assert page.locator("#metrics").inner_text()
                    page.goto(url + "/qa-matrix/index.html", wait_until="load")
                    assert page.locator("#checks select").count() == 24
                    page.locator("#test-0").select_option("Pass")
                    page.reload(wait_until="load")
                    assert page.locator("#test-0").input_value() == "Pass"
                    assert not faults, faults
                    print("BROWSER_SMOKE_PASS", width, height)
                finally:
                    context.close()
        finally:
            browser.close()
    server.shutdown()
