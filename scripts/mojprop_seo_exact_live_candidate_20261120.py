"""Pure patch builder for the exact observed English MOJ PROP static files.

No filesystem, network, deployment, database, payment, or Signal Desk writes.
A caller must independently reverify production inputs and use an approved
release/rollback process. This module cannot itself publish a page.
"""
import hashlib
import html
import json
import re

PAGES = {
    "index.html": (
        "76918c5129ff669ef02f82435a68f61a32d70141800712100d4a7fe9e8554895", "",
        "Moj Prop | Simulated Trading Challenge & Risk Rules",
        "Explore Moj Prop's simulated trading challenge, risk rules and research services. Review current product details and payment terms before deciding.",
        '<a class="btn primary" href="/moj-prop/catalog/">See service prices</a>',
        '<a class="btn soft" href="/moj-prop/starter-30-trx/">Explore Starter 30 — 30 TRX</a>',
    ),
    "catalog/index.html": (
        "b0515a1a2f846e79ed330b9c6ef39b5d75ae1f5e487bf3807c051a9bbac7c21e", "catalog/",
        "Moj Prop Catalog | Simulated Challenge & Research Services",
        "Explore the Moj Prop service catalog, Starter 30 simulated challenge, educational market research and risk rulebooks. Review current terms before deciding.",
        '<a href="/moj-prop/#request">Start a request</a>',
        '<a href="/moj-prop/starter-30-trx/">Starter 30 — 30 TRX</a>',
    ),
    "rules/index.html": (
        "761ec1343df2c1523a2419e03a49acafa086504e52801e8058ce19566b01781c", "rules/",
        "Moj Prop Rulebook | Trading Challenge & Risk Rules",
        "Understand simulated trading evaluation, drawdown limits, risk controls and the published Moj Prop rules. Review current challenge terms before applying.",
        "", "",
    ),
    "payment/index.html": (
        "b6e2c7ac8403c04296956f473daddfe621d06ba3fd7de193633fa4820725c3d4", "payment/",
        "Moj Prop Payment | TRX Invoice & Payment Information",
        "Read Moj Prop payment information, invoice verification guidance and service limitations. Check the current product and payment terms before sending funds.",
        "", "",
    ),
    "contact/index.html": (
        "16d6e4b483d44a6fe8dd245711f6aecbcbf74768e8d90a81318ea6de98d67e9b", "contact/",
        "Contact Moj Prop | Trading Challenge & Research Requests",
        "Contact Moj Prop regarding simulated trading evaluations, research services and published risk rules. Use official contact channels for product questions.",
        "", "",
    ),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def _replace_meta(head, key, value, attribute="name"):
    pattern = r'<meta\b[^>]*\b' + attribute + r'="' + re.escape(key) + r'"[^>]*>'
    tag = f'<meta {attribute}="{key}" content="{html.escape(value, quote=True)}">'
    matches = list(re.finditer(pattern, head, flags=re.I))
    if len(matches) > 1:
        raise ValueError("ambiguous existing metadata")
    if matches:
        match = matches[0]
        return head[:match.start()] + tag + head[match.end():]
    return head + "\n" + tag


def _render(raw, spec):
    _, slug, title, desc, anchor, cta = spec
    text = raw.decode("utf-8", errors="strict")
    if text.count("</head>") != 1 or text.count("</body>") != 1:
        raise ValueError("ambiguous document boundary")
    head, body = text.split("</head>", 1)
    if len(re.findall(r"<title>[^<]*</title>", head, flags=re.I)) != 1:
        raise ValueError("ambiguous title")
    head = re.sub(r"<title>[^<]*</title>",
                  "<title>" + html.escape(title) + "</title>", head, flags=re.I)
    url = "https://mojplaywin.com/moj-prop/" + slug
    canonical_pattern = r'<link\b[^>]*\brel="canonical"[^>]*>'
    canonical = f'<link rel="canonical" href="{url}">'
    if len(re.findall(canonical_pattern, head, flags=re.I)) > 1:
        raise ValueError("ambiguous canonical")
    if re.search(canonical_pattern, head, flags=re.I):
        head = re.sub(canonical_pattern, canonical, head, flags=re.I)
    else:
        head += "\n" + canonical
    for k, v in {"description":desc, "robots":"index,follow,max-image-preview:large",
                 "twitter:card":"summary", "twitter:title":title,
                 "twitter:description":desc}.items():
        head = _replace_meta(head, k, v)
    for k, v in {"og:title":title, "og:description":desc, "og:type":"website",
                 "og:url":url, "og:site_name":"Moj Prop","og:locale":"en_US"}.items():
        head = _replace_meta(head, k, v, "property")
    schema = {"@context":"https://schema.org", "@type":"ContactPage" if slug=="contact/" else "WebPage",
              "@id":url+"#webpage", "url":url, "name":title, "description":desc,
              "inLanguage":"en"}
    if '"@type":"WebPage"' in head or '"@type":"ContactPage"' in head:
        raise ValueError("existing page schema needs review")
    head += '\n<script type="application/ld+json">' + json.dumps(schema, ensure_ascii=True) + "</script>\n"
    if anchor:
        if body.count(anchor) != 1 or "/moj-prop/starter-30-trx/" in body:
            raise ValueError("ambiguous CTA placement")
        body = body.replace(anchor, anchor + "\n" + cta, 1)
    return (head + "</head>" + body).encode("utf-8")


def build_candidate(path, live_bytes):
    """Return reviewed candidate bytes and before/after receipt; reject any drift."""
    if path not in PAGES or type(live_bytes) is not bytes:
        raise ValueError("out of scope or invalid input")
    spec = PAGES[path]
    if sha(live_bytes) != spec[0]:
        raise ValueError("live source differs from observed baseline")
    candidate = _render(live_bytes, spec)
    original_body = live_bytes.split(b"</head>", 1)[1]
    expected_body = original_body
    if spec[4]:
        anchor, cta = spec[4].encode(), spec[5].encode()
        expected_body = original_body.replace(anchor, anchor+b"\n"+cta, 1)
    if candidate.split(b"</head>", 1)[1] != expected_body:
        raise ValueError("unreviewed body change")
    return candidate, {"path":path, "before_sha256":sha(live_bytes),
                       "after_sha256":sha(candidate),
                       "body_before_sha256":sha(original_body),
                       "body_after_sha256":sha(expected_body),
                       "cta_added":bool(spec[4]), "deployment_authorized":False}
