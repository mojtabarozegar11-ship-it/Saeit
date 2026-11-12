"""Idempotent registration of localized financial service routes."""
import ast


def patch_financial_urls(source):
    if "_finance_routes" in source:
        if 'path(f"{_brand_slug}/game/",' not in source:
            source = source.replace(
                'path(f"{_brand_slug}/digital-products/", partial(financial_brand_page, brand=_brand_slug, locale="host", page_type="store"), name=f"finance_{_brand_slug}_store"),',
                'path(f"{_brand_slug}/digital-products/", partial(financial_brand_page, brand=_brand_slug, locale="host", page_type="store"), name=f"finance_{_brand_slug}_store"),\n        path(f"{_brand_slug}/game/", partial(financial_brand_page, brand=_brand_slug, locale="host", page_type="game"), name=f"game_{_brand_slug}"),',
            )
        # Migrate a previously installed finance block in place. This keeps
        # repeated deployments safe while correcting an older store segment.
        return source.replace(
            'path(f"arabic/{_brand_slug}/market-signals/",',
            'path(f"ar/{_brand_slug}/market-signals/",',
        ).replace(
            'path(f"arabic/{_brand_slug}/digital-products/",',
            'path(f"ar/{_brand_slug}/digital-products/",',
        ).replace(
            'path(f"ar/{_brand_slug}/market-signals/",',
            'path(f"ar/{_brand_slug}/market-signals/",',
        ).replace(
            'path(f"ar/{_brand_slug}/digital-products/",',
            'path(f"ar/{_brand_slug}/digital-products/",',
        ).replace(
            'path(f"{_brand_slug}/store/",',
            'path(f"{_brand_slug}/digital-products/",',
        ).replace(
            'path(f"{_brand_slug}/digital-store/",',
            'path(f"{_brand_slug}/digital-products/",',
        ).replace(
            'path(f"ar/{_brand_slug}/store/",',
            'path(f"ar/{_brand_slug}/digital-products/",',
        ).replace(
            'path(f"ar/{_brand_slug}/digital-store/",',
            'path(f"ar/{_brand_slug}/digital-products/",',
        )
    imports = ""
    if "from functools import partial" not in source:
        imports += "from functools import partial\n"
    if "from core.financial_brand_pages import BRANDS, financial_brand_page" not in source:
        imports += "from core.financial_brand_pages import BRANDS, financial_brand_page\n"
    source = imports + source
    tree = ast.parse(source)
    assignment = next((node for node in tree.body
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "urlpatterns"
            for target in node.targets) and isinstance(node.value, (ast.List, ast.Tuple))), None)
    if assignment is None:
        raise ValueError("Expected a literal urlpatterns list")
    block = """
# Add localized branded financial analysis and shop pages ahead of existing routes.
_finance_routes = []
for _brand_slug, _fa, _en, _ar in BRANDS:
    _finance_routes.extend([
        path(f"{_brand_slug}/market-signals/", partial(financial_brand_page, brand=_brand_slug, locale="host", page_type="signals"), name=f"finance_{_brand_slug}_signals"),
        path(f"{_brand_slug}/digital-products/", partial(financial_brand_page, brand=_brand_slug, locale="host", page_type="store"), name=f"finance_{_brand_slug}_store"),
        path(f"{_brand_slug}/game/", partial(financial_brand_page, brand=_brand_slug, locale="host", page_type="game"), name=f"game_{_brand_slug}"),
        path(f"ar/{_brand_slug}/market-signals/", partial(financial_brand_page, brand=_brand_slug, locale="ar", page_type="signals"), name=f"finance_ar_{_brand_slug}_signals"),
        path(f"ar/{_brand_slug}/digital-products/", partial(financial_brand_page, brand=_brand_slug, locale="ar", page_type="store"), name=f"finance_ar_{_brand_slug}_store"),
    ])
urlpatterns = _finance_routes + urlpatterns
"""
    lines = source.splitlines(keepends=True)
    lines.insert(assignment.end_lineno, block)
    result = "".join(lines)
    ast.parse(result)
    return result
