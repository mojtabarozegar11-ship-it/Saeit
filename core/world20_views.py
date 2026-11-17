"""Verified, nonpayable commercial gateway for the 2026 20 largest languages.

A separate Persian business-market locale is intentionally available. This
module does not imply that every linked legacy page has been translated.
No site content or language will silently fall back to English when a
recognized locale's translation is incomplete.
"""
from functools import lru_cache
import json
from pathlib import Path

from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import render

_SCHEMA = "mojplaywin.world20.l1l2.2026.v1"
_RANKED = (
    "en", "zh", "hi", "es", "ar", "fr", "bn", "pt", "id", "ur",
    "ru", "de", "ja", "pcm", "arz", "mr", "vi", "te", "sw", "ha",
)
_SUPPLEMENT = ("fa",)
_RTL = frozenset(("ar", "arz", "ur", "fa"))
_FIELDS = frozenset((
    "name", "direction", "headline", "intro", "prop_title", "prop_body",
    "payment_notice", "prop_link", "fallback_notice", "language_label", "contact_label", "sections", "lead",
))
_SECTION_KEYS = ("prop", "store", "games", "research", "learning", "ai", "company")
_SECTION_PATHS = (
    "/moj-prop/", "/store/", "/studio/", "/research/",
    "/knowledge/", "/agents/", "/company/",
)
_HOSTS = frozenset(("mojplaywin.com", "www.mojplaywin.com"))


@lru_cache(maxsize=1)
def world_catalog():
    source = json.loads(
        Path(__file__).with_name("world20_catalog.json").read_text(encoding="utf-8")
    )
    if source.get("schema") != _SCHEMA:
        raise ValueError("Invalid worldwide language catalogue schema")
    if tuple(source.get("ranked_codes", ())) != _RANKED:
        raise ValueError("Twenty 2026 total-speaker ranking codes must remain stable")
    if tuple(source.get("supplementary_codes", ())) != _SUPPLEMENT:
        raise ValueError("Persian business locale is missing")
    sections = source.get("sections")
    if (not isinstance(sections, list) or
            tuple(x.get("key") for x in sections) != _SECTION_KEYS or
            tuple(x.get("url") for x in sections) != _SECTION_PATHS):
        raise ValueError("Worldwide catalogue has unverified external destinations")
    locales = source.get("locales")
    if type(locales) is not dict or set(locales) != set(_RANKED + _SUPPLEMENT):
        raise ValueError("Incomplete top-20-plus-Persian catalogue")
    for code in _RANKED + _SUPPLEMENT:
        value = locales[code]
        if type(value) is not dict or set(value) != _FIELDS:
            raise ValueError(f"Incomplete translated fields for {code}")
        for field in _FIELDS - {"sections", "lead"}:
            if type(value[field]) is not str or not value[field].strip():
                raise ValueError(f"Untranslated {field} in {code}")
        if value["direction"] != ("rtl" if code in _RTL else "ltr"):
            raise ValueError(f"Wrong writing direction for {code}")
        if (type(value["lead"]) is not dict or
                set(value["lead"]) != {
                    "name", "email", "reason", "consent", "submit", "receipt",
                    "received", "duplicate", "private_token", "failed", "status_link",
                } or any(type(v) is not str or not v.strip()
                         for v in value["lead"].values())):
            raise ValueError(f"Incomplete buyer form copy in {code}")
        if (type(value["sections"]) is not list or
                len(value["sections"]) != len(_SECTION_KEYS) or
                any(type(label) is not str or not label.strip()
                    for label in value["sections"])):
            raise ValueError(f"Missing section navigation in {code}")
    return source


def _headers(response, lang):
    response["Cache-Control"] = "public, max-age=300"
    response["Content-Language"] = lang
    response["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response["X-Frame-Options"] = "DENY"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; "
        "form-action 'none'; base-uri 'none'; frame-ancestors 'none'; "
        "connect-src 'none'; object-src 'none'"
    )
    return response


def _route(request, lang):
    try:
        host = request.get_host().split(":", 1)[0].lower()
    except Exception as exc:
        raise Http404("Invalid MojPlayWin host") from exc
    if host not in _HOSTS or not request.is_secure():
        raise Http404("MojPlayWin HTTPS required")
    if request.META.get("QUERY_STRING", ""):
        raise Http404("No query parameters on canonical translated pages")
    if request.method not in ("GET", "HEAD"):
        return _headers(HttpResponseNotAllowed(["GET", "HEAD"]), lang)
    source = world_catalog()
    if lang not in source["locales"]:
        raise Http404("Unsupported world language")
    translated = source["locales"][lang]
    codes = tuple(source["ranked_codes"]) + tuple(source["supplementary_codes"])
    options = [
        {"code": code, "name": source["locales"][code]["name"],
         "active": code == lang} for code in codes
    ]
    sections = [
        {"key": item["key"], "url": item["url"],
         "label": translated["sections"][index]}
        for index, item in enumerate(source["sections"])
    ]
    response = render(request, "mojplaywin/world20.html", {
        "locale": lang,
        "copy": translated,
        "options": options,
        "sections": sections,
        "canonical": "/world/" + lang + "/",
        "ranking_source": source["ranking_source"],
    }, content_type="text/html; charset=utf-8")
    if request.method == "HEAD":
        response.content = b""
    return _headers(response, lang)


def worldwide_index(request):
    """English default page including every language selector, no redirects."""
    return _route(request, "en")


def worldwide_language(request, lang):
    """Only 2026 ranked languages plus the explicitly selected Persian locale."""
    return _route(request, lang)
