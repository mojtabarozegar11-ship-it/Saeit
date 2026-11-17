"""Hard assertions for 72 client-side structured, non-submitting RFQ drafts."""
import json
from pathlib import Path
import re
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "public/auctions"
DATA = json.loads((ROOT / "content/auctions-72/procurement-notices.json").read_text(encoding="utf-8"))
BASELINE = json.loads((ROOT / "content/auctions-rfq-intake-20261117/baseline.json").read_text(encoding="utf-8"))

FIELDS = ("company", "contact", "reply", "phone", "offer", "capacity", "price", "delivery", "documents", "ack")


class PublicFormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = []
        self.inputs = []
        self.links = []
        self.buttons = []
        self.areas = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self.forms.append(a)
        elif tag == "input":
            self.inputs.append(a)
        elif tag == "a":
            self.links.append(a)
        elif tag == "button":
            self.buttons.append(a)
        elif tag == "textarea":
            self.areas.append(a)


def test_all_72_intake_forms_have_unique_number_and_declared_inputs():
    assert len(DATA["notices"]) == 72
    assert set(BASELINE["baseline_git_blob_sha1"]) == {
        f"public/auctions/{n}/index.html" for n in range(350, 422)
    }
    for n in range(350, 422):
        path = PAGES / str(n) / "index.html"
        markup = path.read_text(encoding="utf-8")
        assert f"zm-rfq-intake-20261117-{n}" in markup
        assert f"zm-auctions-72-v1 official-{n}" in markup
        assert "zm-auctions-seo-20261117-v1" in markup
        assert markup.count(f'id="rfq-offer-form-{n}"') == 1
        assert markup.count(f'id="rfq-offer-preview-{n}" hidden') == 1
        assert f'id="rfq-offer-email-{n}"' in markup
        assert f'id="rfq-offer-copy-{n}"' in markup
        assert f"var n={n}," in markup
        assert "تاکنون ایمیل ارسال" not in markup
        assert "تا وقتی ایمیل را شخصاً ارسال نکنید" in markup
        assert f"شماره رسمی آگهی {n}" in markup
        parser = PublicFormParser()
        parser.feed(markup)
        assert len(parser.forms) == 1
        assert parser.forms[0]["id"] == f"rfq-offer-form-{n}"
        assert not parser.forms[0].get("action")
        assert not parser.forms[0].get("method")
        names = {x["name"] for x in parser.inputs + parser.areas if "name" in x}
        assert names == set(FIELDS), (n, names)
        assert any(x["name"] == "reply" and x["type"] == "email" and "required" in x
                   for x in parser.inputs)
        assert any(x["name"] == "ack" and x["type"] == "checkbox" and "required" in x
                   for x in parser.inputs)
        assert any(x["name"] == "company" and "required" in x for x in parser.inputs)
        assert any(x["name"] == "offer" and "required" in x for x in parser.areas)
        assert any(x.get("href", "").startswith("mailto:zomorodmelal@gmail.com")
                   for x in parser.links)
        assert any(x.get("type") == "submit" for x in parser.buttons)
        assert any(x.get("id") == f"rfq-offer-copy-{n}" for x in parser.buttons)
        assert "فراخوان‌های مرتبط" in markup
        assert 'rel="canonical"' in markup
        assert '"@type":"BreadcrumbList"' in markup
        assert "مهلت پایان ثابت تعیین نشده است" in markup
        assert f"/auctions/{n + (36 if n <= 385 else -36)}/" in markup


def test_no_exfiltration_or_false_submission_statuses():
    for n in range(350, 422):
        page = (PAGES / str(n) / "index.html").read_text(encoding="utf-8")
        scripts = re.findall(r"<script(?:\s[^>]*)?>([\s\S]*?)</script>", page)
        executable = [s for s in scripts if "rfq-offer-form-" in s]
        assert len(executable) == 1, n
        js = executable[0]
        assert "form.reportValidity()" in js
        assert "form.addEventListener(\"submit\"" in js
        assert "ev.preventDefault()" in js
        assert "encodeURIComponent(body)" in js
        assert "navigator.clipboard.writeText" in js
        assert "status.textContent=\"پیش‌نویس آماده شد؛ هنوز به شرکت ارسال نشده است.\"" in js
        for banned in ("fetch(", "XMLHttpRequest", "localStorage", "sessionStorage",
                       "navigator.sendBeacon", "window.location=", "document.cookie",
                       ".submit()", "WebSocket", "<iframe"):
            assert banned not in js, (n, banned)
        assert "mailto:zomorodmelal@gmail.com" in page
        assert "تا وقتی ایمیل را شخصاً ارسال نکنید" in page


def test_supplier_and_equipment_ranges_remain_properly_partitioned():
    notices = DATA["notices"]
    supply = sorted(x["proposed_public_number"] for x in notices if x["kind"] == "supply")
    equipment = sorted(x["proposed_public_number"] for x in notices if x["kind"] == "equipment")
    assert supply == list(range(350, 386))
    assert equipment == list(range(386, 422))
    assert BASELINE["source_main_commit"] == "1b38c32003c8c1a39cb0c9308d29e9ade83d501d"
