#!/usr/bin/env python3
"""Hash-bound, private ChromeDriver smoke QA for the existing SKU 879 website kit.

Only aggregate metrics and an immutable private receipt leave the runner.
No source content, screenshots, DOM text, browser logs or customer data are emitted.
"""
import base64
import hashlib
import http.server
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import zipfile

SKU = 879
SOURCE_SHA = "20894f2de0228318c0e96ba407c2bd4aa98b62ba2f3f2f2fbca53987c9276783"
ROOT = Path("/home/githubops/factory-runtime/private/autonomous-product-cycle/design-intake/mpw-live-three-sku-qa")
SCHEMA = "saeit.mpw.private-browser-smoke-qa.v1"
MAX_UNPACKED = 512 * 1024 * 1024
MAX_MEMBER = 100 * 1024 * 1024


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def safe_extract(archive, destination):
    if not zipfile.is_zipfile(archive):
        raise RuntimeError("ZIP_INVALID")
    total = 0
    html_files = []
    with zipfile.ZipFile(archive) as package:
        infos = package.infolist()
        if not infos or len(infos) > 2000 or package.testzip() is not None:
            raise RuntimeError("ZIP_MEMBERS_OR_CRC_INVALID")
        seen = set()
        for info in infos:
            name = info.filename
            p = PurePosixPath(name)
            mode = (info.external_attr >> 16) & 0o170000
            if (not name or name.startswith("/") or "\\" in name or
                    ".." in p.parts or name in seen or mode in (0o120000, 0o060000, 0o020000)):
                raise RuntimeError("ZIP_UNSAFE_MEMBER")
            seen.add(name)
            if info.file_size > MAX_MEMBER:
                raise RuntimeError("ZIP_MEMBER_TOO_LARGE")
            total += info.file_size
            if total > MAX_UNPACKED:
                raise RuntimeError("ZIP_EXPANSION_LIMIT")
            target = destination.joinpath(*p.parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True, mode=0o700)
                continue
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            count = 0
            with package.open(info) as reader, target.open("xb") as writer:
                while True:
                    block = reader.read(1024 * 1024)
                    if not block:
                        break
                    count += len(block)
                    if count > MAX_MEMBER or count > info.file_size:
                        raise RuntimeError("ZIP_MEMBER_SIZE_MISMATCH")
                    writer.write(block)
            os.chmod(target, 0o600)
            if name.lower().endswith((".html", ".htm")):
                html_files.append(name)
    indexes = [name for name in html_files if PurePosixPath(name).name.lower() == "index.html"]
    if not indexes:
        raise RuntimeError("WEBSITE_INDEX_MISSING")
    return sorted(indexes, key=lambda name: (len(PurePosixPath(name).parts), name))[0]


def get_port():
    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        return connection.getsockname()[1]


def webdriver_request(port, method, route, data=None):
    encoded = None if data is None else json.dumps(data).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:" + str(port) + route, encoded, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=28) as response:
            result = json.load(response)
    except Exception as exc:
        raise RuntimeError("WEBDRIVER_REQUEST_" + type(exc).__name__) from None
    value = result.get("value")
    if isinstance(value, dict) and value.get("error"):
        raise RuntimeError("WEBDRIVER_REPORTED_ERROR")
    return value


def screenshot_is_png(value):
    try:
        raw = base64.b64decode(value, validate=True)
        if len(raw) < 1000 or raw[:8] != b"\x89PNG\r\n\x1a\n":
            return False
        width, height = struct.unpack(">II", raw[16:24])
        return width >= 300 and height >= 300
    except Exception:
        return False


METRICS_JS = r"""
for (const image of document.images) image.loading = "eager";
const root = document.documentElement;
const body = document.body;
const images = Array.from(document.images);
const visibleWidth = window.visualViewport?.width || window.innerWidth;
function inFixedLayer(node) {
  for (let cur = node; cur && cur !== body; cur = cur.parentElement)
    if (getComputedStyle(cur).position === "fixed") return true;
  return false;
}
function buttonHasName(b) {
  if ((b.getAttribute("aria-label") || "").trim()) return true;
  if ((b.getAttribute("title") || "").trim()) return true;
  if ((b.innerText || "").trim()) return true;
  const refs = (b.getAttribute("aria-labelledby") || "").trim().split(/\s+/).filter(Boolean);
  if (refs.some(id => (document.getElementById(id)?.textContent || "").trim())) return true;
  if (Array.from(b.querySelectorAll("img[alt]")).some(i => (i.alt || "").trim())) return true;
  if (Array.from(b.querySelectorAll("svg title")).some(t => (t.textContent || "").trim())) return true;
  return false;
}
function samePageAnchorResolves(a) {
  const href = a.getAttribute("href") || "";
  if (href === "#" || href.length === 0) return true;
  let fragment = "";
  try { fragment = decodeURIComponent(href.slice(1)); }
  catch { return false; }
  if (fragment.toLowerCase() === "top") return true;
  return !!document.getElementById(fragment) ||
    Array.from(document.querySelectorAll("a[name]")).some(el => el.getAttribute("name") === fragment);
}
return {
    ready: document.readyState === "complete",
    title_present: !!document.title.trim(),
    body_char_count: ((body && body.innerText) || "").trim().length,
    image_count: images.length,
    broken_images: images.filter(i => !i.complete || i.naturalWidth === 0).length,
    viewport_width: window.innerWidth,
    viewport_height: window.innerHeight,
    device_screen_width: screen.width,
    visual_viewport_width: Math.round((window.visualViewport?.width || 0) * 100) / 100,
    visual_viewport_scale: window.visualViewport?.scale || 0,
    viewport_meta_present: !!document.querySelector('meta[name="viewport"]'),
    viewport_meta_device_width: Array.from(document.querySelectorAll('meta[name="viewport"]')).some(
      m => /width\s*=\s*device-width/i.test(m.content || "")),
    viewport_meta_count: document.querySelectorAll('meta[name="viewport"]').length,
    root_min_width: getComputedStyle(root).minWidth,
    body_min_width: getComputedStyle(body).minWidth,
    body_scroll_width: body.scrollWidth,
    root_scroll_width: root.scrollWidth,
    horizontal_overflow_px: Math.max(0, root.scrollWidth - visibleWidth),
    overflowing_shapes: Array.from(body.querySelectorAll("*"))
      .map(node => ({ node, rect: node.getBoundingClientRect() }))
      .filter(item => item.rect.width > 0 && item.rect.right > visibleWidth + 2 &&
                      item.rect.left < visibleWidth && !inFixedLayer(item.node))
      .sort((a, b) => b.rect.right - a.rect.right)
      .slice(0, 12)
      .map(item => ({
        tag: item.node.tagName.toLowerCase(),
        right_px: Math.round(item.rect.right),
        width_px: Math.round(item.rect.width),
        left_px: Math.round(item.rect.left),
        position: getComputedStyle(item.node).position,
        display: getComputedStyle(item.node).display,
        min_width: getComputedStyle(item.node).minWidth,
        white_space: getComputedStyle(item.node).whiteSpace,
        overflow_x: getComputedStyle(item.node).overflowX,
        flex_shrink: getComputedStyle(item.node).flexShrink,
        box_sizing: getComputedStyle(item.node).boxSizing
      })),
    h1_count: document.querySelectorAll("h1").length,
    images_missing_alt: images.filter(i => !i.hasAttribute("alt")).length,
    unlabeled_buttons: Array.from(document.querySelectorAll("button")).filter(
      b => !buttonHasName(b)).length,
    unlabeled_form_controls: Array.from(document.querySelectorAll("input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=reset]):not([type=image]),textarea,select")).filter(
      el => !(el.getAttribute("aria-label") || "").trim() &&
            !(el.getAttribute("aria-labelledby") || "").trim() &&
            !(el.labels && el.labels.length)).length,
    unsafe_blank_links: Array.from(document.querySelectorAll('a[target="_blank"]')).filter(
      a => !(a.relList && a.relList.contains("noopener"))).length,
    broken_same_page_anchors: Array.from(document.querySelectorAll('a[href^="#"]')).filter(
      a => !samePageAnchorResolves(a)).length
};
"""


def browser_views(destination, entrypoint, sizes=None):
    sizes = ((390, 844), (1440, 900)) if sizes is None else tuple(sizes)
    if not sizes or len(sizes) > 16 or any(
            not isinstance(w, int) or not isinstance(h, int) or
            w < 280 or w > 2400 or h < 400 or h > 1600
            for w, h in sizes):
        raise RuntimeError("BROWSER_VIEWPORT_SET_INVALID")
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    driver = shutil.which("chromedriver")
    if not chrome or not driver:
        raise RuntimeError("CHROME_OR_DRIVER_UNAVAILABLE")
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(destination), **kwargs)
        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    driver_port = get_port()
    service = None
    session_id = None
    profile_temp = None
    try:
        profile_temp = tempfile.TemporaryDirectory(prefix="mpw879-chrome-profile-")
        profile = profile_temp.name
        service = subprocess.Popen(
            [driver, "--port=" + str(driver_port), "--allowed-ips=127.0.0.1", "--silent"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        for _ in range(60):
            if service.poll() is not None:
                raise RuntimeError("CHROMEDRIVER_EARLY_EXIT")
            try:
                webdriver_request(driver_port, "GET", "/status")
                break
            except RuntimeError:
                time.sleep(0.25)
        else:
            raise RuntimeError("CHROMEDRIVER_START_TIMEOUT")
        options = {
            "args": [
                "--headless=new", "--no-sandbox", "--disable-gpu",
                "--disable-dev-shm-usage", "--disable-background-networking",
                "--disable-extensions", "--no-first-run",
                "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1",
                "--user-data-dir=" + profile,
            ],
            "binary": chrome,
        }
        created = webdriver_request(driver_port, "POST", "/session", {
            "capabilities": {"alwaysMatch": {
                "browserName": "chrome", "goog:chromeOptions": options
            }}
        })
        session_id = created.get("sessionId") if isinstance(created, dict) else None
        if not session_id:
            raise RuntimeError("WEBDRIVER_SESSION_MISSING")
        route = "/session/" + urllib.parse.quote(session_id, safe="")
        url = ("http://127.0.0.1:" + str(server.server_port) + "/" +
               urllib.parse.quote(entrypoint, safe="/"))
        rows = []
        for width, height in sizes:
            webdriver_request(driver_port, "POST", route + "/window/rect",
                              {"width": max(width, 850), "height": max(height, 900)})
            webdriver_request(driver_port, "POST", route + "/goog/cdp/execute", {
                "cmd": "Emulation.setDeviceMetricsOverride",
                "params": {"width": width, "height": height, "deviceScaleFactor": 1,
                           "mobile": width < 500}
            })
            webdriver_request(driver_port, "POST", route + "/url", {"url": url})
            webdriver_request(driver_port, "POST", route + "/execute/sync",
                              {"script": 'for (const i of document.images) i.loading="eager";', "args": []})
            time.sleep(0.7)
            metrics = webdriver_request(driver_port, "POST", route + "/execute/sync",
                                        {"script": METRICS_JS, "args": []})
            if not isinstance(metrics, dict):
                raise RuntimeError("WEBDRIVER_METRICS_INVALID")
            png = webdriver_request(driver_port, "GET", route + "/screenshot")
            rows.append({
                "requested_viewport": [width, height],
                "ready": metrics.get("ready") is True,
                "title_present": metrics.get("title_present") is True,
                "body_char_count": int(metrics.get("body_char_count", 0)),
                "image_count": int(metrics.get("image_count", 0)),
                "broken_images": int(metrics.get("broken_images", 0)),
                "viewport_width": int(metrics.get("viewport_width", 0)),
                "viewport_height": int(metrics.get("viewport_height", 0)),
                "device_screen_width": int(metrics.get("device_screen_width", 0)),
                "visual_viewport_width": float(metrics.get("visual_viewport_width", 0)),
                "visual_viewport_scale": float(metrics.get("visual_viewport_scale", 0)),
                "viewport_meta_present": metrics.get("viewport_meta_present") is True,
                "viewport_meta_device_width": metrics.get("viewport_meta_device_width") is True,
                "viewport_meta_count": int(metrics.get("viewport_meta_count", 0)),
                "root_min_width": str(metrics.get("root_min_width", ""))[:32],
                "body_min_width": str(metrics.get("body_min_width", ""))[:32],
                "body_scroll_width": int(metrics.get("body_scroll_width", 0)),
                "root_scroll_width": int(metrics.get("root_scroll_width", 0)),
                "overflowing_shapes": metrics.get("overflowing_shapes", []),
                "horizontal_overflow_px": int(metrics.get("horizontal_overflow_px", 100000)),
                "h1_count": int(metrics.get("h1_count", 0)),
                "images_missing_alt": int(metrics.get("images_missing_alt", 0)),
                "unlabeled_buttons": int(metrics.get("unlabeled_buttons", 0)),
                "unlabeled_form_controls": int(metrics.get("unlabeled_form_controls", 0)),
                "unsafe_blank_links": int(metrics.get("unsafe_blank_links", 0)),
                "broken_same_page_anchors": int(metrics.get("broken_same_page_anchors", 0)),
                "screenshot_valid": screenshot_is_png(png),
            })
        return rows
    finally:
        if service is not None:
            if session_id:
                try:
                    webdriver_request(driver_port, "DELETE",
                                      "/session/" + urllib.parse.quote(session_id, safe=""))
                except RuntimeError:
                    pass
            service.terminate()
            try:
                service.wait(timeout=6)
            except subprocess.TimeoutExpired:
                service.kill()
                service.wait(timeout=3)
        # Chrome can still be writing into its user-data directory until the
        # WebDriver session and driver process are closed. Clean the profile
        # only after both have been stopped.
        if profile_temp is not None:
            profile_temp.cleanup()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def audit(archive, expected_sha=SOURCE_SHA, output=None):
    archive = Path(archive)
    if sha256_file(archive) != expected_sha or expected_sha != SOURCE_SHA:
        raise RuntimeError("PRIVATE_BROWSER_SOURCE_HASH_MISMATCH")
    with tempfile.TemporaryDirectory(prefix="mpw879-browser-qa-") as temp:
        entrypoint = safe_extract(archive, Path(temp))
        views = browser_views(Path(temp), entrypoint)
    checks = {
        "two_real_browser_viewports": len(views) == 2,
        "viewport_dimensions_verified": len(views) == 2 and all(
            v["viewport_height"] == v["requested_viewport"][1] and
            (v["device_screen_width"] == v["requested_viewport"][0] and
             abs(v["visual_viewport_width"] - v["requested_viewport"][0]) <= 1
             if v["requested_viewport"][0] < 500 else
             v["viewport_width"] == v["requested_viewport"][0])
            for v in views),
        "dom_ready_and_titled": bool(views) and all(v["ready"] and v["title_present"] for v in views),
        "visible_page_content": bool(views) and all(v["body_char_count"] >= 30 for v in views),
        "no_horizontal_overflow": bool(views) and all(v["horizontal_overflow_px"] <= 2 for v in views),
        "all_html_images_loaded": bool(views) and all(v["broken_images"] == 0 for v in views),
        "screenshots_rendered_privately": bool(views) and all(v["screenshot_valid"] for v in views),
    }
    result = {
        "schema": SCHEMA, "sku": SKU, "source_sha256": expected_sha,
        "entrypoint_sha256": sha256_bytes(entrypoint.encode("utf-8")),
        "checks": checks, "views": views, "browser_smoke_passed": all(checks.values()),
        "professional_quality_score": None, "quality1000_verified": False,
        "commercial_release_allowed": False, "live_product_modified": False,
        "specialist_review_remaining": [
            "visual_design_quality", "real_user_navigation", "cross-browser_mobile",
            "dynamic_functionality", "accessibility_wcag", "security_threat_model",
            "license_and_rights_version_mapping"
        ],
    }
    raw = (json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if output is not None:
        Path(output).write_bytes(raw)
        os.chmod(output, 0o600)
    print("MPW_SKU879_PRIVATE_BROWSER_QA=" + json.dumps({
        "source_sha256": expected_sha, "checks_passed": sum(checks.values()),
        "checks_total": len(checks), "failed_checks": [k for k,v in checks.items() if not v],
        "viewport_count": len(views),
        "viewport_overflow_diagnostics": [{
            "requested_width": v["requested_viewport"][0],
            "actual_width": v["viewport_width"],
            "horizontal_overflow_px": v["horizontal_overflow_px"],
            "device_screen_width": v["device_screen_width"],
            "visual_viewport_width": v["visual_viewport_width"],
            "visual_viewport_scale": v["visual_viewport_scale"],
            "viewport_meta_present": v["viewport_meta_present"],
            "viewport_meta_device_width": v["viewport_meta_device_width"],
            "viewport_meta_count": v["viewport_meta_count"],
            "root_min_width": v["root_min_width"],
            "body_min_width": v["body_min_width"],
            "body_scroll_width": v["body_scroll_width"],
            "root_scroll_width": v["root_scroll_width"],
            "offenders": v["overflowing_shapes"]
        } for v in views],
        "browser_smoke_passed": result["browser_smoke_passed"],
        "quality1000_verified": False, "commercial_release_allowed": False
    }, sort_keys=True))
    return result


def ingest(root=ROOT, source=sys.stdin.buffer):
    raw = source.read(50001)
    if not raw or len(raw) > 50000:
        raise RuntimeError("BROWSER_QA_RECEIPT_SIZE_INVALID")
    receipt = json.loads(raw)
    if (receipt.get("schema") != SCHEMA or receipt.get("sku") != SKU or
            receipt.get("source_sha256") != SOURCE_SHA or
            receipt.get("quality1000_verified") is not False or
            receipt.get("commercial_release_allowed") is not False or
            receipt.get("live_product_modified") is not False or
            not isinstance(receipt.get("checks"), dict) or
            not isinstance(receipt.get("views"), list) or
            receipt.get("browser_smoke_passed") is not all(receipt["checks"].values())):
        raise RuntimeError("BROWSER_QA_RECEIPT_IDENTITY_INVALID")
    original = root / "copies" / str(SKU) / (SOURCE_SHA + ".bin")
    if original.is_symlink() or not original.is_file() or sha256_file(original) != SOURCE_SHA:
        raise RuntimeError("BROWSER_QA_PRIVATE_SOURCE_NOT_VERIFIED")
    folder = root / "quality1000-rework" / str(SKU) / SOURCE_SHA / "browser-audits"
    if folder.is_symlink():
        raise RuntimeError("BROWSER_QA_DESTINATION_UNSAFE")
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(folder, 0o700)
    receipt_sha = sha256_bytes(raw)
    target = folder / (receipt_sha + ".json")
    if target.is_symlink():
        raise RuntimeError("BROWSER_QA_TARGET_SYMLINK")
    if target.exists():
        if target.read_bytes() != raw:
            raise RuntimeError("BROWSER_QA_RECEIPT_CONFLICT")
        created = False
    else:
        fd, temporary = tempfile.mkstemp(prefix=".browser-qa-", dir=folder)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            try:
                os.link(temporary, target)
                created = True
            except FileExistsError:
                if target.read_bytes() != raw:
                    raise RuntimeError("BROWSER_QA_RECEIPT_CONFLICT")
                created = False
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    print("MPW_SKU879_PRIVATE_BROWSER_RECEIPT=" + json.dumps({
        "source_sha256": SOURCE_SHA, "receipt_sha256": receipt_sha,
        "created": created, "browser_smoke_passed": receipt["browser_smoke_passed"],
        "quality1000_verified": False, "commercial_release_allowed": False
    }, sort_keys=True))
    return receipt_sha


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "ingest":
        ingest()
    elif len(sys.argv) == 5 and sys.argv[1] == "audit":
        report = audit(sys.argv[2], sys.argv[3], sys.argv[4])
        raise SystemExit(0 if report["browser_smoke_passed"] else 2)
    else:
        raise SystemExit("USAGE_ERROR")
