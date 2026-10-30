#!/usr/bin/env python3
"""G-01 to S-01: read-only, loopback-only browser UI smoke gate.
No checkout clicks, POST, credentials, screenshots, external URLs or live mutations.
Usage: python g01_s01_local_browser_accessibility_gate_r43.py --root ./snapshot --page index.html
"""
import argparse
import functools
import http.server
import json
import threading
from pathlib import Path

def safe_page(root: Path, page: str) -> Path:
    if page.startswith('/') or '\\' in page or '?' in page or '#' in page:
        raise ValueError('Page must be a plain relative path')
    path = (root / page).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file() or path.suffix.lower() not in {'.html', '.htm'}:
        raise ValueError('Page must be an existing HTML file inside root')
    return path

def run(root: Path, page: str) -> dict:
    safe_page(root, page)
    from playwright.sync_api import sync_playwright
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    url = origin + '/' + page
    out = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                for name, width, height, mobile in [('desktop', 1365, 850, False), ('mobile', 390, 844, True)]:
                    context = browser.new_context(viewport={'width': width, 'height': height}, is_mobile=mobile, has_touch=mobile, service_workers='block')
                    context.route('**/*', lambda route: route.continue_() if route.request.method == 'GET' and route.request.url.startswith(origin + '/') else route.abort())
                    page_obj = context.new_page()
                    errors = []
                    page_obj.on('pageerror', lambda error: errors.append(str(error)))
                    response = page_obj.goto(url, wait_until='domcontentloaded', timeout=20000)
                    if not response or response.status >= 400:
                        raise RuntimeError(f'{name}: failed to load local HTML')
                    result = page_obj.evaluate("""() => {
                      const visible = e => !!e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden';
                      const controls = [...document.querySelectorAll('button,input,select,textarea')].filter(visible);
                      const unlabeled = controls.filter(e => !e.disabled && !(e.getAttribute('aria-label') || e.getAttribute('aria-labelledby') || e.labels?.length || e.textContent?.trim() || e.title));
                      const ids = [...document.querySelectorAll('[id]')].map(e => e.id);
                      return {title:document.title, visible_controls:controls.length, unlabeled_controls:unlabeled.length, duplicate_ids:ids.length-new Set(ids).size, horizontal_overflow:document.documentElement.scrollWidth>innerWidth+2};
                    }""")
                    result.update(viewport=name, js_errors=errors)
                    out.append(result)
                    context.close()
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
    if any(r['unlabeled_controls'] or r['duplicate_ids'] or r['horizontal_overflow'] or r['js_errors'] for r in out):
        raise RuntimeError('UI gate failed: ' + json.dumps(out, ensure_ascii=False))
    return {'status': 'LOCAL_BROWSER_UI_PASS', 'page': page, 'viewports': out, 'production_checked': False}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--page', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.root.resolve(), args.page), ensure_ascii=False, indent=2))
