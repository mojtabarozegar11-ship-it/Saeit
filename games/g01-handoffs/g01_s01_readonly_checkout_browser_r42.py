#!/usr/bin/env python3
"""S-01 handoff: strictly read-only, explicit-host desktop/mobile checkout UI probe.
No purchase clicks, no payment, no credential input, no screenshots or customer data.
Usage: python g01_s01_readonly_checkout_browser_r41.py --url https://STAGING_HOST/path --allow-host STAGING_HOST
"""
import argparse
import json
from urllib.parse import urlparse


def validate_target(url: str, allowed_host: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        raise ValueError('Absolute HTTP(S) URL required')
    if parsed.username or parsed.password or parsed.fragment or parsed.query:
        raise ValueError('Credentials, query and fragment are forbidden')
    if parsed.hostname != allowed_host:
        raise ValueError('Explicit allow-host must match target hostname')
    if parsed.scheme != 'https' and parsed.hostname not in ('localhost', '127.0.0.1'):
        raise ValueError('Plain HTTP is only permitted for local staging')
    return parsed.hostname


SAFE_RESOURCE_TYPES = frozenset(('document', 'stylesheet', 'script', 'image', 'font', 'media'))


def permitted_request(method: str, request_url: str, resource_type: str, host: str, initial_url: str) -> bool:
    parsed = urlparse(request_url)
    if method != 'GET' or parsed.hostname != host or parsed.scheme not in ('http', 'https'):
        return False
    if resource_type not in SAFE_RESOURCE_TYPES:
        return False  # Never permit XHR/fetch, beacons, websocket or POST checkout calls.
    if resource_type == 'document' and request_url != initial_url:
        return False  # No subframe or scripted navigation to potentially mutating GET endpoints.
    return True


def run(url: str, host: str) -> dict:
    validate_target(url, host)
    from playwright.sync_api import sync_playwright
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for name, width, height, mobile in [('desktop', 1365, 850, False), ('mobile', 390, 844, True)]:
                context = browser.new_context(viewport={'width': width, 'height': height}, is_mobile=mobile, has_touch=mobile, service_workers='block')
                page = context.new_page()
                blocked = []

                def guard(route):
                    req = route.request
                    if not permitted_request(req.method, req.url, req.resource_type, host, url):
                        blocked.append({'method': req.method, 'kind': req.resource_type})
                        route.abort()
                    else:
                        route.continue_()

                page.route('**/*', guard)
                response = page.goto(url, wait_until='domcontentloaded', timeout=25000)
                if not response or response.status >= 400:
                    raise RuntimeError(f'{name}: HTTP status invalid')
                ui = page.evaluate("""() => {
                  const visible = e => !!(e.getClientRects().length) && getComputedStyle(e).visibility !== 'hidden';
                  const controls = [...document.querySelectorAll('button,input,select,textarea')].filter(visible);
                  const nameless = controls.filter(e => !(e.getAttribute('aria-label') || e.getAttribute('aria-labelledby') || e.labels?.length || e.textContent?.trim() || e.title));
                  const ids = [...document.querySelectorAll('[id]')].map(e => e.id);
                  return {title: document.title, controls: controls.length, nameless: nameless.length, duplicate_ids: ids.length-new Set(ids).size, forms: document.forms.length, horizontal_overflow: document.documentElement.scrollWidth > innerWidth+2};
                }""")
                # Navigation and UI only: no submit, no cart mutation, no authentication.
                if ui['nameless'] or ui['duplicate_ids'] or ui['horizontal_overflow']:
                    raise RuntimeError(f'{name}: accessibility/layout contract failed: {ui}')
                results.append({'device': name, 'http_status': response.status, **ui, 'blocked_requests': len(blocked)})
                context.close()
        finally:
            browser.close()
    return {'result': 'READ_ONLY_STATIC_UI_PROBE_PASS_NOT_CHECKOUT_E2E', 'url_host': host, 'checks': results}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', required=True)
    ap.add_argument('--allow-host', required=True)
    args = ap.parse_args()
    try:
        print(json.dumps(run(args.url, args.allow_host), ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({'result': 'BLOCKED', 'error': type(exc).__name__ + ': ' + str(exc)}, ensure_ascii=False))
        raise SystemExit(2)


if __name__ == '__main__':
    main()
