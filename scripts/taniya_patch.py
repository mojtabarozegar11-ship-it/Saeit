"""Fail-closed AST-guided edits for the MojPlayWin Taniya page."""

import ast

STUDIO_LINK_OLD = '"links":[{"title":"هوش مصنوعی","text":"ابزارهای AI برای تولید","url":"/agents/"},{"title":"اقتصاد","text":"اقتصاد محصولات دیجیتال","url":"/economy/"},{"title":"آموزش","text":"آموزش و مهارت","url":"/education/"}]'
STUDIO_LINK_NEW = '"links":[{"title":"Taniya Studio","text":"20 playful browser games","url":"/taniya/"},{"title":"هوش مصنوعی","text":"ابزارهای AI برای تولید","url":"/agents/"},{"title":"اقتصاد","text":"اقتصاد محصولات دیجیتال","url":"/economy/"},{"title":"آموزش","text":"آموزش و مهارت","url":"/education/"}]'


def _urlpatterns(tree):
    matches = []
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(target, ast.Name) and target.id == "urlpatterns" for target in targets):
            value = node.value
            if isinstance(value, (ast.List, ast.Tuple)):
                matches.extend(
                    item for item in value.elts
                    if isinstance(item, ast.Call)
                    and isinstance(item.func, ast.Name)
                    and item.func.id == "path"
                    and item.args
                    and isinstance(item.args[0], ast.Constant)
                    and isinstance(item.args[0].value, str)
                )
    return matches


def patch_urls(text):
    tree = ast.parse(text)
    routes = _urlpatterns(tree)
    studio = [route for route in routes if route.args[0].value == "studio/"]
    taniya = [route for route in routes if route.args[0].value == "taniya/"]
    if len(studio) != 1 or len(taniya) > 1:
        raise ValueError("Expected one studio route and at most one Taniya route")

    imports = [
        node for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "core.views"
    ]
    if not imports:
        raise ValueError("Expected a direct import from core.views")
    bound_names = {
        alias.asname or alias.name
        for node in imports for alias in node.names
    }
    if "platform_page" not in bound_names:
        raise ValueError("Expected platform_page from core.views")
    if "taniya_studio" not in bound_names:
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
        lines.insert(assignment.lineno - 1, "from core.views import taniya_studio\n")
        text = "".join(lines)
        tree = ast.parse(text)
        routes = _urlpatterns(tree)
        studio = [route for route in routes if route.args[0].value == "studio/"]
        taniya = [route for route in routes if route.args[0].value == "taniya/"]
        if len(studio) != 1 or len(taniya) > 1:
            raise ValueError("Unexpected route source")

    if taniya:
        route = taniya[0]
        if not (len(route.args) >= 2 and isinstance(route.args[1], ast.Name)
                and route.args[1].id == "taniya_studio"):
            raise ValueError("Existing Taniya route has an unexpected target")
        return text

    route = studio[0]
    lines = text.splitlines(keepends=True)
    line = lines[route.lineno - 1]
    indent = line[:len(line) - len(line.lstrip())]
    addition = f'{indent}path("taniya/", taniya_studio, name="taniya_studio"),\n'
    lines.insert(route.end_lineno, addition)
    return "".join(lines)


def patch_views(text):
    tree = ast.parse(text)
    existing = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == "taniya_studio"]
    if existing:
        if len(existing) != 1:
            raise ValueError("Found duplicate Taniya views")
        source = ast.get_source_segment(text, existing[0]) or ""
        if 'render(request, "taniya_studio/index.html")' not in source:
            raise ValueError("Existing Taniya view has an unexpected body")
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
    block = (
        f"{decorator}def taniya_studio(request):\n"
        '    return render(request, "taniya_studio/index.html")\n\n\n'
    )
    lines = text.splitlines(keepends=True)
    lines.insert(platform[0].lineno - 1, block)
    patched = "".join(lines)

    if STUDIO_LINK_OLD in patched:
        patched = patched.replace(STUDIO_LINK_OLD, STUDIO_LINK_NEW, 1)
    return patched
