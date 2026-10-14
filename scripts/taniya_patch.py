"""Fail-closed, idempotent source edits for the MojPlayWin Taniya page."""

URL_IMPORT_OLD = "from core.views import home, platform_page"
URL_IMPORT_NEW = "from core.views import home, platform_page, taniya_studio"
STUDIO_PATH_OLD = '    path("studio/", lambda request: platform_page(request, "studio"), name="studio"),'
STUDIO_PATH_NEW = STUDIO_PATH_OLD + '\n    path("taniya/", taniya_studio, name="taniya_studio"),'

STUDIO_LINK_OLD = '"links":[{"title":"هوش مصنوعی","text":"ابزارهای AI برای تولید","url":"/agents/"},{"title":"اقتصاد","text":"اقتصاد محصولات دیجیتال","url":"/economy/"},{"title":"آموزش","text":"آموزش و مهارت","url":"/education/"}]'
STUDIO_LINK_NEW = '"links":[{"title":"Taniya Studio","text":"20 playful browser games","url":"/taniya/"},{"title":"هوش مصنوعی","text":"ابزارهای AI برای تولید","url":"/agents/"},{"title":"اقتصاد","text":"اقتصاد محصولات دیجیتال","url":"/economy/"},{"title":"آموزش","text":"آموزش و مهارت","url":"/education/"}]'
VIEW_BLOCK = (
    "@never_cache\\n"
    "def taniya_studio(request):\\n"
    '    return render(request, "taniya_studio/index.html")\\n'
    "\\n\\n"
)

def _ensure(text, old, new, label):
    if new in text:
        return text
    if text.count(old) != 1:
        raise ValueError(f"Expected exactly one {label} anchor")
    return text.replace(old, new, 1)

def patch_urls(text):
    if "from django.views.decorators" not in text:
        raise ValueError("Unexpected URL source")
    text = _ensure(text, URL_IMPORT_OLD, URL_IMPORT_NEW, "views import")
    text = _ensure(text, STUDIO_PATH_OLD, STUDIO_PATH_NEW, "studio route")
    return text

def patch_views(text):
    if "from django.views.decorators.cache import never_cache" not in text:
        raise ValueError("Expected never_cache import in views")
    if "def taniya_studio(request):" not in text:
        marker = "def platform_page(request, section):"
        if text.count(marker) != 1:
            raise ValueError("Expected exactly one platform_page anchor")
        addition = VIEW_BLOCK + marker
        text = text.replace(marker, addition, 1)
    elif 'return render(request, "taniya_studio/index.html")' not in text:
        raise ValueError("Found an unexpected Taniya view")
    text = _ensure(text, STUDIO_LINK_OLD, STUDIO_LINK_NEW, "studio link")
    return text
