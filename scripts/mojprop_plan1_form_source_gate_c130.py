#!/usr/bin/env python3
"""C130: read-only source gate for the distinct MOJ-PROP-01 opt-in URL.

Catches links to an unmounted backend and query parameters the canonical GET
view will reject. No network, Django startup, secrets, PII, customer POST,
database, email, payment or deploy. Source parity != live Passenger readiness.
"""
from __future__ import annotations

import ast
from html.parser import HTMLParser
from pathlib import Path
import sys
from urllib.parse import urlsplit, parse_qsl

FORM = "/moj-prop-interest/form/"
POST = "/moj-prop-interest/"
PAGES = ("templates/moj-prop/contact/index.html", "templates/moj-prop-v4/index.html")
KEYS = (
    "landing_and_contact_query_contract",
    "dedicated_get_route_mapped",
    "dedicated_post_route_mapped",
    "dedicated_view_guards_present",
    "consent_template_present",
    "consent_model_and_migration_present",
    "django_app_registered",
    "model_import_registered",
    "migration_chain_complete",
    "source_ready",
)
MAX_SOURCE = 1024 * 1024


def _read(root: Path, relative: str) -> str:
    path = root / relative
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_SOURCE:
            return ""
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError, ValueError):
        return ""


class _Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.hrefs.append(dict(attrs).get("href", ""))


def _canonical_links(html: str) -> bool:
    if not html:
        return False
    try:
        parser = _Links()
        parser.feed(html)
        parser.close()
    except (TypeError, ValueError):
        return False
    candidates = [href for href in parser.hrefs
                  if "moj-prop-interest/form/" in href]
    if len(candidates) < 2 or len(candidates) > 20:
        return False
    found = []
    for href in candidates:
        if not isinstance(href, str) or any(ord(c) < 32 for c in href):
            return False
        try:
            url = urlsplit(href)
            params = parse_qsl(url.query, keep_blank_values=True, strict_parsing=True)
        except ValueError:
            return False
        if url.path != FORM or url.scheme or url.netloc or url.fragment:
            return False
        if params not in ([], [("lang", "fa")]):
            return False
        found.append((url.path, tuple(params)))
    return (set(found) == {(FORM, ()), (FORM, (("lang", "fa"),))}
            and len(found) >= 2)


def _source_routes(urls: str) -> tuple[bool, bool]:
    try:
        tree = ast.parse(urls)
    except SyntaxError:
        return False, False
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "core.moj_prop_views":
            imports.update(alias.name for alias in node.names)
    mapped: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id != "path" or len(node.args) < 2:
            continue
        route, view = node.args[:2]
        if isinstance(route, ast.Constant) and isinstance(route.value, str):
            mapped.setdefault(route.value, []).append(
                view.id if isinstance(view, ast.Name) else ""
            )
    def linked(route: str, name: str) -> bool:
        return mapped.get(route.lstrip("/")) == [name] and name in imports
    return linked(FORM, "moj_prop_interest_form"), linked(POST, "moj_prop_interest")


def _decorators(function: ast.FunctionDef) -> set[str]:
    result = set()
    for decorator in function.decorator_list:
        if isinstance(decorator, ast.Name):
            result.add(decorator.id)
        elif isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
            result.add(decorator.func.id)
    return result


def _view_guards(source: str) -> bool:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    funcs = {node.name: node for node in tree.body
             if isinstance(node, ast.FunctionDef)}
    get = funcs.get("moj_prop_interest_form")
    post = funcs.get("moj_prop_interest")
    if get is None or post is None:
        return False
    get_src = ast.get_source_segment(source, get) or ""
    post_src = ast.get_source_segment(source, post) or ""
    return bool(
        {"csrf_protect", "never_cache"} <= _decorators(get)
        and {"csrf_protect", "require_POST"} <= _decorators(post)
        and all(token in get_src for token in
                ("request.is_secure()", "request.get_host()", "request.GET",
                 '"lang"', '"GET"', '"HEAD"', "status=400"))
        and all(token in post_src for token in
                ("request.is_secure()", "request.get_host()", "contact_consent",
                 "MOJ-PROP-01", "PropInterest"))
    )



def _installed_prop_app(settings: str, app_source: str) -> bool:
    """Reject comment-only mentions of installed apps or unregistered AppConfig."""
    try:
        cfg = ast.parse(settings)
        app_ast = ast.parse(app_source)
        active = False
        for node in cfg.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "INSTALLED_APPS"
                for target in node.targets
            ):
                installed = ast.literal_eval(node.value)
                active = (type(installed) is list
                          and installed.count("prop_firm.apps.MojPropConfig") == 1)
        configured = any(
            isinstance(node, ast.ClassDef) and node.name == "MojPropConfig"
            and any(
                isinstance(child, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "name"
                        for target in child.targets)
                and isinstance(child.value, ast.Constant)
                and child.value.value == "prop_firm"
                for child in node.body
            )
            for node in app_ast.body
        )
        return active and configured
    except (SyntaxError, ValueError, TypeError, RecursionError):
        return False


def _model_exported(source: str) -> bool:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    return any(
        isinstance(node, ast.ImportFrom) and node.level == 1
        and node.module == "lead_models"
        and any(alias.name == "PropInterest" for alias in node.names)
        for node in tree.body
    )


def _migration_depends_on_previous(source: str) -> bool:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Migration":
            for child in node.body:
                if isinstance(child, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == "dependencies"
                    for target in child.targets
                ):
                    try:
                        deps = ast.literal_eval(child.value)
                    except (ValueError, TypeError, RecursionError):
                        return False
                    return deps == [("prop_firm", "0007_equity_broker_source")]
    return False


def evaluate(root: Path) -> dict[str, bool]:
    pages = [_read(root, path) for path in PAGES]
    get_route, post_route = _source_routes(_read(root, "config/urls.py"))
    template = _read(root, "core/templates/mojplaywin/moj_prop_interest_form_d.html")
    model = _read(root, "prop_firm/lead_models.py")
    migration = _read(root, "prop_firm/migrations/0008_prospect_contact_intake.py")
    settings = _read(root, "config/settings.py")
    app_config = _read(root, "prop_firm/apps.py")
    registered_models = _read(root, "prop_firm/models.py")
    evidence = {
        "landing_and_contact_query_contract": all(_canonical_links(page) for page in pages),
        "dedicated_get_route_mapped": get_route,
        "dedicated_post_route_mapped": post_route,
        "dedicated_view_guards_present": _view_guards(_read(root, "core/moj_prop_views.py")),
        "consent_template_present": all(token in template for token in
            ('action="/moj-prop-interest/"', "{% csrf_token %}",
             'name="email"', 'name="contact_consent"', "MOJ-PROP-01")),
        "consent_model_and_migration_present": (
            "class PropInterest(" in model
            and 'name="PropInterest"' in migration
            and "contact_consent" not in migration
        ),
        "django_app_registered": _installed_prop_app(settings, app_config),
        "model_import_registered": _model_exported(registered_models),
        "migration_chain_complete": (
            _migration_depends_on_previous(migration)
            and _read(root, "prop_firm/migrations/0007_equity_broker_source.py") != ""
        ),
    }
    evidence["source_ready"] = all(evidence.values())
    return evidence


def main(argv: list[str]) -> int:
    if len(argv) > 2 or (len(argv) == 2 and argv[1] != "--require-source-ready"):
        raise SystemExit("usage: c130.py [--require-source-ready]")
    result = evaluate(Path.cwd())
    for key in KEYS:
        print("MOJPROP_C130_" + key.upper() + "=" + str(result[key]).lower())
    print("MOJPROP_C130_LIVE_PASSENGER_PARITY_PROVEN=false")
    print("MOJPROP_C130_CONSENTED_BUYER_POST_VERIFIED=false")
    print("MOJPROP_C130_PAYMENT_OR_DEPLOYMENT=false")
    if len(argv) == 2 and not result["source_ready"]:
        return 3  # manual release preflight must never bypass unmounted route
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
