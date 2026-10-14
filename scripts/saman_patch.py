"""Fail-closed Django route edits for the MojPlayWin SAMAN page."""

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
    saman = [route for route in routes if route.args[0].value == "saman/"]
    if len(saman) > 1:
        raise ValueError("Found duplicate SAMAN routes")
    if saman:
        route = saman[0]
        if not (len(route.args) >= 2 and isinstance(route.args[1], ast.Name)
                and route.args[1].id == "saman_page"):
            raise ValueError("Existing SAMAN route has an unexpected target")
        return text

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
        tree = ast.parse(text)
        routes = _routes(tree)

    candidates = [route for route in routes if route.args[0].value in {"studio/", "taniya/"}]
    anchor = candidates[-1] if candidates else (routes[-1] if routes else None)
    if anchor is None:
        raise ValueError("Expected at least one existing route to anchor SAMAN")
    lines = text.splitlines(keepends=True)
    line = lines[anchor.lineno - 1]
    indent = line[:len(line) - len(line.lstrip())]
    lines.insert(anchor.end_lineno, f'{indent}path("saman/", saman_page, name="saman_page"),\n')
    patched = "".join(lines)
    ast.parse(patched)
    return patched


def patch_views(text):
    tree = ast.parse(text)
    existing = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == "saman_page"]
    if existing:
        if len(existing) != 1:
            raise ValueError("Found duplicate SAMAN views")
        source = ast.get_source_segment(text, existing[0]) or ""
        if 'render(request, "saman/index.html")' not in source:
            raise ValueError("Existing SAMAN view has an unexpected body")
        return text

    platform = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == "platform_page"]
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
    never_cache = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "django.views.decorators.cache"
        and any((alias.asname or alias.name) == "never_cache" for alias in node.names)
        for node in tree.body
    )
    decorator = "@never_cache\n" if never_cache else ""
    block = f'{decorator}def saman_page(request):\n    return render(request, "saman/index.html")\n\n\n'
    lines = text.splitlines(keepends=True)
    lines.insert(platform[0].lineno - 1, block)
    patched = "".join(lines)
    ast.parse(patched)
    return patched
