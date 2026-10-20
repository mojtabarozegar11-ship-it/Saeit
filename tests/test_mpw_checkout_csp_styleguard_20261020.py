"""Offline regression proofs for the MojPlayWin CSP two-style checkout repair.

These never access the production server, customer orders, or payment rails.
"""
import base64
import hashlib
import importlib.util
from pathlib import Path

import pytest

PATCH = Path(__file__).resolve().parents[1] / "scripts" / "mpw_checkout_csp_styleguard_live_20261020.py"
spec = importlib.util.spec_from_file_location("mpw_csp_guard_patch", PATCH)
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)


def original_source():
    return (
        "def _apply_two_book_strict_csp(response):\n"
        "    import base64, hashlib, re\n"
        "    body = response.content\n"
        "    scripts = re.findall(rb\"<script(?:\\s[^>]*)?>(.*?)</script\\s*>\", body, re.I | re.S)\n"
        "    styles = re.findall(rb\"<style(?:\\s[^>]*)?>(.*?)</style\\s*>\", body, re.I | re.S)\n"
        "    " + patch.OLD1 + "\n"
        "        raise RuntimeError('Checkout markup changed; CSP cannot be safely hashed')\n"
        "    def source_hash(raw):\n"
        "        return \"'sha256-\" + base64.b64encode(hashlib.sha256(raw).digest()).decode('ascii') + \"'\"\n"
        "    policy = (\n"
        "        \"default-src 'none'; \"\n"
        "        \"script-src 'self' \" + source_hash(scripts[0]) + \"; \"\n"
        "        " + patch.OLD2 + "\n"
        "        \"connect-src 'self'; object-src 'none'; base-uri 'self';\"\n"
        "    )\n"
        "    tag = ('<meta http-equiv=\"Content-Security-Policy\" content=\"' + policy + '\">').encode('ascii')\n"
        "    response.content = body.replace(b'<meta charset=\"utf-8\">', b'<meta charset=\"utf-8\">\\n' + tag, 1)\n"
        "    response['X-Robots-Tag'] = 'noindex, nofollow'\n"
        "    return response\n"
    )


def compiled_handler():
    original = original_source().encode("utf8")
    result, method_src = patch.build(original)
    assert patch.OLD1.encode() not in result
    assert patch.OLD2.encode() not in result
    namespace = {}
    exec(compile(method_src, "csp_test", "exec"), namespace)
    return namespace["_apply_two_book_strict_csp"]


class FakeResponse:
    def __init__(self, body):
        self.content = body
        self.headers = {}
    def __setitem__(self, key, value):
        self.headers[key] = value


def page(styles=2, scripts=1):
    return (
        b'<html><head><meta charset="utf-8">'
        + b"".join(b"<style>" + str(i).encode() + b"{color:gold}</style>" for i in range(styles))
        + b"</head><body>"
        + b"".join(b"<script>const pay=" + str(i).encode() + b";</script>" for i in range(scripts))
        + b"</body></html>"
    )


def test_two_styles_one_script_render_without_weakening_csp():
    handler = compiled_handler()
    response = handler(FakeResponse(page()))
    text = response.content.decode()
    assert text.count("sha256-") == 3
    expected = [
        base64.b64encode(hashlib.sha256(s).digest()).decode()
        for s in (b"const pay=0;", b"0{color:gold}", b"1{color:gold}")
    ]
    assert all("sha256-" + digest in text for digest in expected)
    assert "unsafe-inline" not in text and "unsafe-eval" not in text
    assert "default-src 'none'" in text and "object-src 'none'" in text
    assert text.count("Content-Security-Policy") == 1
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow"


@pytest.mark.parametrize("styles,scripts", [(0, 1), (3, 1), (2, 0), (2, 2)])
def test_noncompliant_markup_remains_blocked(styles, scripts):
    handler = compiled_handler()
    with pytest.raises(RuntimeError, match="CSP cannot be safely hashed"):
        handler(FakeResponse(page(styles, scripts)))


def test_existing_one_style_checkout_still_supported():
    handler = compiled_handler()
    response = handler(FakeResponse(page(styles=1)))
    assert response.content.count(b"sha256-") == 2


def test_unrelated_source_does_not_accept_surgical_patch():
    with pytest.raises(RuntimeError, match="implementation not found"):
        patch.build(b"def unrelated_function():\n    pass\n")
