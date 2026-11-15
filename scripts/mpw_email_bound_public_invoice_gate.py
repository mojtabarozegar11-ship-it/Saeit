"""Pure read-only public HTTPS TRX invoice page gate.

Reject missing, duplicate, disabled, prefilled or detached email, CSRF or
submit controls. Does not submit orders or call a payment or mail endpoint.
"""
from html.parser import HTMLParser
import re


class EmailBoundInvoiceMarkupGate(HTMLParser):
    EMAIL_FIELDS = frozenset((
        "email", "buyer_email", "customer_email", "purchase_email",
        "purchaser_email",
    ))

    def __init__(self, *, product_id):
        super().__init__(convert_charrefs=True)
        self.action = f"/commerce/trx-easy/start/{product_id}/"
        self.forms = 0
        self.csrf = 0
        self.email = 0
        self.submit = 0
        self.current = False
        self.bad = False

    def handle_starttag(self, tag, pairs):
        names = [k.casefold() for k,_ in pairs if k]
        if len(names) != len(set(names)) or any(k.startswith("on") for k in names):
            self.bad = True
        attrs = dict((k.casefold(),v) for k,v in pairs if k)
        if tag in ("script","iframe","object","embed","base"):
            self.bad = True
        if tag == "form":
            if self.current or self.forms:
                self.bad = True
            self.forms += 1
            self.current = True
            if (attrs.get("method","").casefold() != "post"
                    or attrs.get("action") != self.action
                    or "target" in attrs or "novalidate" in attrs):
                self.bad = True
            return
        if tag not in ("input","button"):
            return
        name = (attrs.get("name") or "").casefold().strip()
        typ = (attrs.get("type") or ("submit" if tag == "button" else "text")).casefold()
        active = not ("disabled" in attrs or "readonly" in attrs or
                      "hidden" in attrs or "inert" in attrs)
        if (name in self.EMAIL_FIELDS or typ == "email"
                or "email" in (attrs.get("id") or "").casefold()):
            if not self.current:
                self.bad = True
            self.email += 1
            if (tag != "input" or name not in self.EMAIL_FIELDS or typ != "email"
                    or not active or "required" not in attrs or "multiple" in attrs
                    or attrs.get("value")
                    or attrs.get("autocomplete","email") not in ("email","")
                    or attrs.get("maxlength") not in ("254",None)):
                self.bad = True
        elif name == "csrfmiddlewaretoken":
            if not self.current:
                self.bad = True
            self.csrf += 1
            value = attrs.get("value") or ""
            if (tag != "input" or typ != "hidden" or "disabled" in attrs
                    or len(value) not in (32,64) or not value.isascii()
                    or not value.isalnum()):
                self.bad = True
        if typ == "submit":
            self.submit += 1
            if not self.current or tag not in ("input","button") or not active:
                self.bad = True
        if any(k in attrs for k in (
                "formaction","formenctype","formmethod","formtarget","formnovalidate")):
            self.bad = True

    def handle_endtag(self, tag):
        if tag == "form":
            if not self.current:
                self.bad = True
            self.current = False

    @property
    def approved_structure(self):
        return (not self.bad and not self.current and self.forms == 1
                and self.csrf == 1 and self.email == 1 and self.submit == 1)


def has_guarded_guest_email_invoice_form(body: bytes, product_id: int) -> bool:
    if (type(product_id) is not int or product_id < 1
            or type(body) is not bytes or not 150 <= len(body) <= 250_000):
        return False
    parser = EmailBoundInvoiceMarkupGate(product_id=product_id)
    try:
        parser.feed(body.decode("utf-8","strict"))
        parser.close()
    except (UnicodeError, TypeError, ValueError):
        return False
    return parser.approved_structure
