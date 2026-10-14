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


def patch_urls(text):
    tree = ast.parse(text)
    routes = _routes(tree)
    if not routes:
        raise ValueError("Expected at least one existing route")
    saman = [route for route in routes if route.args[0].value == "saman/"]
    if len(saman) > 1:
        raise ValueError("Found duplicate SAMAN routes")
    if saman:
        route = saman[0]
        if not (len(route.args) >= 2 and isinstance(route.args[1], ast.Name)
                and route.args[1].id == "saman_page"):
            raise ValueError("Existing SAMAN route has an unexpected target")
    else:
        candidates = [route for route in routes if route.args[0].value in {"studio/", "taniya/"}]
        anchor = candidates[-1] if candidates else routes[-1]
        lines = text.splitlines(keepends=True)
        line = lines[anchor.lineno - 1]
        indent = line[:len(line) - len(line.lstrip())]
        lines.insert(anchor.end_lineno, f'{indent}path("saman/", saman_page, name="saman_page"),\n')
        text = "".join(lines)
        tree = ast.parse(text)

    imports = [node for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == "core.views"]
    bound_names = {alias.asname or alias.name for node in imports for alias in node.names}
    if "saman_page" not in bound_names:
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
        lines.insert(assignment.lineno - 1, "from core.views import saman_page\n")
        text = "".join(lines)

    ast.parse(text)
    return text


def patch_views(text):
    tree = ast.parse(text)
    existing = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "saman_page"
    ]
    if len(existing) > 1:
        raise ValueError("Found duplicate SAMAN views")

    render_imported = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "django.shortcuts"
        and any((alias.asname or alias.name) == "render" for alias in node.names)
        for node in tree.body
    )
    if not render_imported:
        raise ValueError("Expected render import from django.shortcuts")
    never_cache_imported = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "django.views.decorators.cache"
        and any((alias.asname or alias.name) == "never_cache" for alias in node.names)
        for node in tree.body
    )

    body = (
        "def saman_page(request):\n"
        "    from django.http import Http404\n"
        "    section = request.GET.get(\"section\", \"home\")\n"
        "    allowed = {\"home\", \"learn\", \"play\", \"products\", \"membership\", \"partners\", \"about\"}\n"
        "    if section not in allowed:\n"
        "        raise Http404\n"
        "    return render(request, \"saman/index.html\", {\"saman_section\": section})\n"
    )
    decorator = "@never_cache\n" if never_cache_imported else ""
    replacement = decorator + body

    if existing:
        node = existing[0]
        source = ast.get_source_segment(text, node) or ""
        if 'render(request, "saman/index.html", {"saman_section": section})' in source:
            return text
        if 'render(request, "saman/index.html")' not in source:
            raise ValueError("Existing SAMAN view has an unexpected body")
        start = min([node.lineno] + [item.lineno for item in node.decorator_list])
        lines = text.splitlines(keepends=True)
        lines[start - 1:node.end_lineno] = [replacement + "\n"]
        patched = "".join(lines)
        ast.parse(patched)
        return patched

    platform = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "platform_page"
    ]
    if len(platform) != 1:
        raise ValueError("Expected exactly one platform_page view")
    lines = text.splitlines(keepends=True)
    lines.insert(platform[0].lineno - 1, replacement + "\n\n")
    patched = "".join(lines)
    ast.parse(patched)
    return patched
