"""Fail-closed route and view patch for Studio Raham."""
import ast


def _urls(tree):
    result=[]
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t,ast.Name) and t.id=="urlpatterns" for t in node.targets):
            if isinstance(node.value,(ast.List,ast.Tuple)):
                for item in node.value.elts:
                    if isinstance(item,ast.Call) and isinstance(item.func,ast.Name) and item.func.id=="path" and item.args and isinstance(item.args[0],ast.Constant) and isinstance(item.args[0].value,str):
                        result.append(item)
    return result


def patch_urls(text):
    tree=ast.parse(text)
    imports=[n for n in tree.body if isinstance(n,ast.ImportFrom) and n.module=="core.views"]
    names={a.asname or a.name for n in imports for a in n.names}
    if not imports or "platform_page" not in names:
        raise ValueError("Expected the existing core.views platform_page import")
    routes=_urls(tree)
    existing=[r for r in routes if r.args[0].value=="studio.Roham/"]
    studio=[r for r in routes if r.args[0].value=="studio/"]
    if len(existing)>1 or len(studio)!=1:
        raise ValueError("Expected exactly one existing studio route and at most one Studio Raham route")
    if existing:
        route=existing[0]
        if len(route.args)<2 or not isinstance(route.args[1],ast.Name) or route.args[1].id!="studio_raha":
            raise ValueError("Existing Studio Raham route has an unexpected target")
        if "studio_raha" not in names:
            raise ValueError("Existing route is missing its view import")
        return text
    lines=text.splitlines(keepends=True)
    import_node=imports[0]
    if import_node.lineno!=import_node.end_lineno:
        raise ValueError("Refusing to rewrite a multiline core.views import")
    line=lines[import_node.lineno-1]
    if "studio_raha" not in names:
        lines[import_node.lineno-1]=line.rstrip("\r\n")+", studio_raha\n"
    tree=ast.parse("".join(lines))
    routes=_urls(tree)
    studio=[r for r in routes if r.args[0].value=="studio/"]
    if len(studio)!=1: raise ValueError("Studio route changed during patch")
    route=studio[0]
    line=lines[route.lineno-1]
    indent=line[:len(line)-len(line.lstrip())]
    lines.insert(route.end_lineno, f'{indent}path("studio.Roham/", studio_raha, name="studio_raha"),\n')
    patched="".join(lines)
    ast.parse(patched)
    return patched


def patch_views(text):
    tree=ast.parse(text)
    existing=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name=="studio_raha"]
    if existing:
        if len(existing)!=1 or 'render(request, "studio_raha/index.html")' not in (ast.get_source_segment(text,existing[0]) or ""):
            raise ValueError("Existing Studio Raham view has an unexpected body")
        return text
    has_render=any(isinstance(n,ast.ImportFrom) and n.module=="django.shortcuts" and any((a.asname or a.name)=="render" for a in n.names) for n in tree.body)
    has_never_cache=any(isinstance(n,ast.ImportFrom) and n.module=="django.views.decorators.cache" and any((a.asname or a.name)=="never_cache" for a in n.names) for n in tree.body)
    if not has_render or not has_never_cache:
        raise ValueError("Expected existing render and never_cache imports")
    platform=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name=="platform_page"]
    if len(platform)!=1: raise ValueError("Expected exactly one platform_page function")
    block='@never_cache\ndef studio_raha(request):\n    return render(request, "studio_raha/index.html")\n\n\n'
    lines=text.splitlines(keepends=True)
    lines.insert(platform[0].lineno-1,block)
    result="".join(lines)
    ast.parse(result)
    return result
