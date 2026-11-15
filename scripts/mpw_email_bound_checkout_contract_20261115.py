"""Strict public form contract for email-owned TRON guest checkout.

Read-only inspection: no invoice creation, wallet calls, payments or mail.
The legacy cutover remains blocked until live schema and rollback are proven.
"""
import html
from html.parser import HTMLParser


def _normalized(value):
    text = str(value or "")
    for _ in range(4):
        next_text = html.unescape(text)
        if next_text == text:
            break
        text = next_text
    return text.strip().casefold()


def _action(value):
    """HTTP path matching is case-sensitive; normalizing case hides broken URLs."""
    if type(value) is not str:
        return ""
    return html.unescape(value).strip()


class _EmailBoundCheckoutForm(HTMLParser):
    def __init__(self, action):
        super().__init__(convert_charrefs=True)
        self.action = action
        self.active = None
        self.valid_forms = 0
        self.email_inputs = 0
        self.invalid = False

    def handle_starttag(self, tag, attrs):
        names = [str(key).casefold() for key, _ in attrs]
        if len(names) != len(set(names)):
            self.invalid = True
        fields = {str(key).casefold(): value for key, value in attrs}
        if tag == "form":
            if self.active is not None:
                self.invalid = True
            if ("novalidate" in fields or "target" in fields
                    or _normalized(fields.get("enctype") or "application/x-www-form-urlencoded")
                    != "application/x-www-form-urlencoded"
                    or _normalized(fields.get("accept-charset") or "utf-8") != "utf-8"):
                self.invalid = True
            self.active = {
                "target": _action(fields.get("action")) == self.action,
                "post": _normalized(fields.get("method")) == "post",
                "csrf": 0,
                "email": 0,
            }
        elif tag == "input":
            if self.active is not None and any(
                key in fields for key in ("form", "formaction", "formmethod",
                                          "formtarget", "formenctype",
                                          "formnovalidate")
            ):
                self.invalid = True
            name = _normalized(fields.get("name"))
            typ = _normalized(fields.get("type"))
            field_id = _normalized(fields.get("id"))
            auto = _normalized(fields.get("autocomplete"))
            is_email = any("email" in x for x in (name, typ, field_id, auto))
            if is_email:
                self.email_inputs += 1
                # One required blank email field on the invoice POST form,
                # never a hidden, disabled, or prefilled second identity.
                if (self.active is None or not self.active["target"]
                        or not self.active["post"] or name != "email"
                        or typ != "email" or "required" not in fields
                        or "disabled" in fields or "readonly" in fields
                        or "multiple" in fields
                        or _normalized(fields.get("value"))
                        or self.active["email"]):
                    self.invalid = True
                else:
                    self.active["email"] += 1
            if name == "csrfmiddlewaretoken":
                if (self.active is None or not self.active["target"]
                        or not self.active["post"] or typ != "hidden"
                        or "disabled" in fields
                        or not (fields.get("value") or "").strip()
                        or self.active["csrf"]):
                    self.invalid = True
                else:
                    self.active["csrf"] += 1

        elif tag == "button" and self.active is not None:
            if any(key in fields for key in (
                "form", "formaction", "formmethod", "formtarget",
                "formenctype", "formnovalidate",
            )):
                self.invalid = True

    def handle_endtag(self, tag):
        if tag == "form":
            if self.active is None:
                self.invalid = True
                return
            if self.active["target"]:
                if (self.active["post"] and self.active["csrf"] == 1
                        and self.active["email"] == 1):
                    self.valid_forms += 1
                else:
                    self.invalid = True
            self.active = None

    @property
    def verified(self):
        return (not self.invalid and self.active is None
                and self.valid_forms == 1 and self.email_inputs == 1)


def has_email_bound_guest_invoice_form(body, product_id):
    """Proof of rendered required-email markup, NOT server ownership or payment."""
    if type(product_id) is not int or product_id <= 0 or type(body) is not bytes:
        return False
    scanner = _EmailBoundCheckoutForm(f"/commerce/trx-easy/start/{product_id}/")
    try:
        scanner.feed(body.decode("utf-8"))
        scanner.close()
    except (UnicodeDecodeError, ValueError):
        return False
    return scanner.verified
