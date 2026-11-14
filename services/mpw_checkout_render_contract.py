"""Fail-closed HTML contract for MojPlayWin guest invoice entry.

Only validates a *locally rendered* Django HTML response before it is returned.
It neither changes a template nor sends any request or buyer information.
Never treats an HTML form as proof that an order is payable or delivered.
"""
from __future__ import annotations

from html.parser import HTMLParser

MAX_CHECKOUT_BYTES = 512_000
EMAIL_FIELDS = frozenset({
    "email", "buyer_email", "customer_email", "purchase_email",
    "purchaser_email",
})
OVERRIDE_ATTRIBUTES = frozenset({
    "formaction", "formmethod", "formenctype", "formtarget", "formnovalidate",
})


class CheckoutMarkupError(ValueError):
    """A fixed, non-sensitive reason to hold an unusable checkout page."""


class _CheckoutParser(HTMLParser):
    def __init__(self, expected_action: str):
        super().__init__(convert_charrefs=True)
        self.expected_action = expected_action
        self.errors = set()
        self.form = None
        self.post_count = 0
        self.good_post_count = 0
        self.csrf_values = []
        self.email_inputs = []
        self.submit_count = 0
        self.script_count = 0

    @staticmethod
    def _attrs(attributes):
        names = [name.casefold() for name, _ in attributes if name]
        return names, {name.casefold(): value for name, value in attributes if name}

    def handle_starttag(self, tag, attributes):
        names, attrs = self._attrs(attributes)
        if any(name.startswith("on") for name in names):
            self.errors.add("inline_event_handler")
        if any(isinstance(value, str) and value.lstrip().casefold().startswith(
                ("javascript:", "vbscript:", "data:text/html"))
               for value in attrs.values()):
            self.errors.add("active_url")
        if tag in {"script", "iframe", "object", "embed", "base"}:
            self.errors.add("executable_or_base_element")
            if tag == "script":
                self.script_count += 1
        if tag == "meta" and (attrs.get("http-equiv") or "").strip().casefold() == "refresh":
            self.errors.add("meta_refresh")
        if tag == "form":
            if self.form is not None:
                self.errors.add("nested_forms")
            method = (attrs.get("method") or "get").strip().casefold()
            if method == "post":
                self.post_count += 1
            if (method != "post" or attrs.get("action") != self.expected_action
                    or "target" in attrs or "novalidate" in attrs
                    or ("enctype" in attrs and (attrs.get("enctype") or "").strip().casefold()
                        != "application/x-www-form-urlencoded")
                    or ("accept-charset" in attrs and
                        (attrs.get("accept-charset") or "").strip().casefold() != "utf-8")):
                self.errors.add("invalid_form")
            if names.count("action") != 1 or names.count("method") != 1:
                self.errors.add("duplicate_or_missing_form_keys")
            self.form = {"csrf": [], "email": [], "submit": 0}
            return
        if self.form is None:
            # Detached inputs cannot validate the invoice's own POST.
            if tag in {"input", "button"} and ("form" in attrs or
                    (attrs.get("name") or "").casefold() in EMAIL_FIELDS):
                self.errors.add("detached_buyer_control")
            return
        if tag not in {"input", "button", "textarea", "select"}:
            return
        if any(name in OVERRIDE_ATTRIBUTES for name in names) or "form" in names:
            self.errors.add("submit_override")
        if any(names.count(key) > 1 for key in
               ("name", "value", "type", "required", "disabled", "readonly", "id")):
            self.errors.add("duplicate_control_attribute")
        name = (attrs.get("name") or "").strip().casefold()
        kind = (attrs.get("type") or ("submit" if tag == "button" else "text")).casefold()
        if tag == "input" and name == "csrfmiddlewaretoken":
            self.form["csrf"].append((kind, attrs.get("value"), "disabled" in attrs))
        if (name in EMAIL_FIELDS or kind == "email"
                or "email" in (attrs.get("id") or "").casefold()
                or (attrs.get("autocomplete") or "").casefold() == "email"):
            # Browsers truncate values at maxlength; too-small inputs make
            # a valid customer contact impossible even if required is set.
            if "maxlength" in attrs:
                try:
                    limit = int(attrs.get("maxlength"))
                    if not 6 <= limit <= 254:
                        self.errors.add("buyer_email_length_limit")
                except (TypeError, ValueError):
                    self.errors.add("buyer_email_length_limit")
            self.form["email"].append((
                tag, name, kind, "required" in attrs,
                "disabled" in attrs or "readonly" in attrs or "multiple" in attrs,
            ))
        if (tag == "button" and kind == "submit"
                or tag == "input" and kind == "submit"):
            if "disabled" not in attrs and "hidden" not in attrs:
                self.form["submit"] += 1
        if tag == "input" and kind == "image":
            self.errors.add("image_submit")

    def handle_endtag(self, tag):
        if tag != "form":
            return
        if self.form is None:
            self.errors.add("orphan_form_closer")
            return
        self.good_post_count += 1
        self.csrf_values.extend(self.form["csrf"])
        self.email_inputs.extend(self.form["email"])
        self.submit_count += self.form["submit"]
        self.form = None


def checkout_markup_category(response, product_id: int) -> str:
    """Return only fixed labels, never raw HTML, CSRF, email or invoice data."""
    if type(product_id) is not int or product_id <= 0:
        return "invalid_product"
    if getattr(response, "status_code", None) != 200 or getattr(
            response, "streaming", False):
        return "response_not_rendered_html"
    content = getattr(response, "content", None)
    if not isinstance(content, bytes) or not 150 <= len(content) <= MAX_CHECKOUT_BYTES:
        return "checkout_body_unreadable"
    try:
        html = content.decode("utf-8", "strict")
    except UnicodeDecodeError:
        return "checkout_body_unreadable"
    parser = _CheckoutParser(f"/commerce/trx-easy/start/{product_id}/")
    try:
        parser.feed(html)
        parser.close()
    except (ValueError, TypeError):
        return "checkout_markup_unparseable"
    if parser.errors or parser.form is not None or parser.script_count:
        return "checkout_active_or_ambiguous_markup"
    if parser.post_count != 1 or parser.good_post_count != 1:
        return "checkout_post_form_unverified"
    if len(parser.csrf_values) != 1:
        return "checkout_csrf_unverified"
    kind, token, disabled = parser.csrf_values[0]
    if (kind != "hidden" or disabled or not isinstance(token, str)
            or len(token) not in (32, 64) or not token.isascii()
            or not token.isalnum()):
        return "checkout_csrf_unverified"
    if len(parser.email_inputs) != 1:
        return "checkout_buyer_email_unverified"
    tag, name, kind, required, blocked = parser.email_inputs[0]
    if tag != "input" or name not in EMAIL_FIELDS or kind != "email" or not required or blocked:
        return "checkout_buyer_email_unverified"
    if parser.submit_count != 1:
        return "checkout_submit_unverified"
    return "rendered_form_structurally_valid_not_paid"


def require_checkout_markup(response, product_id: int) -> None:
    if checkout_markup_category(response, product_id) != "rendered_form_structurally_valid_not_paid":
        raise CheckoutMarkupError("Buyer checkout form not ready")
