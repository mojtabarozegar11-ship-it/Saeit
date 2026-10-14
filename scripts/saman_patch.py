"""Fail-closed Django route edits for the MojPlayWin SAMAN site."""

import ast


def _routes(tree):
    routes = []
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(target, ast.Name) and target.id == "urlpatterns" for target in targets):
            value = node.value
            if isinstance(value, (ast.List, ast.Tuple)):
                routes.extend(
                    item for item in value.elts
                    if isinstance(item, ast.Call)
                    and isinstance(item.func, ast.Name)
                    and item.func.id == "path"
                    and item.args
                    and isinstance(item.args[0], ast.Constant)
                    and isinstance(item.args[0].value, str)
                )
    return routes


def _route_target(route, name):
    return (
        len(route.args) >= 2
        and isinstance(route.args[1], ast.Name)
        and route.args[1].id == name
    )


def _insert_route(text, route, line_anchor):
    lines = text.splitlines(keepends=True)
    line = lines[line_anchor.lineno - 1]
    indent = line[:len(line) - len(line.lstrip())]
    lines.insert(line_anchor.end_lineno, f"{indent}{route}\n")
    return "".join(lines)


def patch_urls(text):
    tree = ast.parse(text)
    routes = _routes(tree)
    if not routes:
        raise ValueError("Expected at least one existing route")

    base_routes = [route for route in routes if route.args[0].value == "saman/"]
    section_routes = [
        route for route in routes
        if route.args[0].value == "saman/<slug:section>/"
    ]
    if len(base_routes) > 1 or len(section_routes) > 1:
        raise ValueError("Found duplicate SAMAN routes")
    if base_routes and not _route_target(base_routes[0], "saman_page"):
        raise ValueError("Existing SAMAN route has an unexpected target")
    if section_routes and not _route_target(section_routes[0], "saman_section_page"):
        raise ValueError("Existing SAMAN section route has an unexpected target")

    required_imports = {"saman_page", "saman_section_page"}
    imports = [
        node for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "core.views"
    ]
    bound_names = {alias.asname or alias.name for node in imports for alias in node.names}
    missing_imports = sorted(required_imports - bound_names)
    if missing_imports:
        assignment = next(
            (node for node in tree.body
             if isinstance(node, (ast.Assign, ast.AnnAssign))
             and any(isinstance(target, ast.Name) and target.id == "urlpatterns"
                     for target in (node.targets if isinstance(node, ast.Assign) else [node.target]))),
            None,
        )
        if assignment is None:
            raise ValueError("Expected urlpatterns")
        lines = text.splitlines(keepends=True)
        for name in missing_imports:
            lines.insert(assignment.lineno - 1, f"from core.views import {name}\n")
        text = "".join(lines)
        tree = ast.parse(text)
        routes = _routes(tree)
        base_routes = [route for route in routes if route.args[0].value == "saman/"]
        section_routes = [route for route in routes if route.args[0].value == "saman/<slug:section>/"]

    if not base_routes:
        candidates = [route for route in routes if route.args[0].value in {"studio/", "taniya/"}]
        anchor = candidates[-1] if candidates else routes[-1]
        text = _insert_route(text, 'path("saman/", saman_page, name="saman_page"),', anchor)
        tree = ast.parse(text)
        routes = _routes(tree)
        base_routes = [route for route in routes if route.args[0].value == "saman/"]

    if not section_routes:
        text = _insert_route(
            text,
            'path("saman/<slug:section>/", saman_section_page, name="saman_section"),',
            base_routes[0],
        )

    ast.parse(text)
    return text


def patch_views(text):
    tree = ast.parse(text)
    existing = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "saman_section_page"
    ]
    if existing:
        if len(existing) != 1:
            raise ValueError("Found duplicate SAMAN section views")
        source = ast.get_source_segment(text, existing[0]) or ""
        if 'render(request, "saman/index.html", {"saman_section": section})' not in source:
            raise ValueError("Existing SAMAN section view has an unexpected body")
        return text

    platform = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "platform_page"
    ]
    if len(platform) != 1:
        raise ValueError("Expected exactly one platform_page view")
    render_imported = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "django.shortcuts"
        and any((alias.asname or alias.name) == "render" for alias in node.names)
        for node in tree.body
    )
    if not render_imported:
        raise ValueError("Expected render import from django.shortcuts")

    block = (
        "def saman_section_page(request, section):\n"
        "    from django.http import Http404\n"
        "    allowed = {\"learn\", \"play\", \"shop\", \"membership\", \"partners\", \"about\"}\n"
        "    if section not in allowed:\n"
        "        raise Http404\n"
        "    return render(request, \"saman/index.html\", {\"saman_section\": section})\n\n\n"
    )
    lines = text.splitlines(keepends=True)
    lines.insert(platform[0].lineno - 1, block)
    patched = "".join(lines)
    ast.parse(patched)
    return patched
