#!/usr/bin/env python3
"""Read-only audit of local visual dependencies referenced by the public homepage.

Reports bounded counts only, never paths, CSS, HTML, user data, or private files.
This is a safety preflight, not a change to the public website.
"""
from __future__ import annotations

from html.parser import HTMLParser
import os
from pathlib import Path
import posixpath
import re
import sys
from urllib.parse import unquote, urlsplit

PUBLIC = Path("/home/zomorod2/public_html")
VISUAL_EXTS = {".css", ".js", ".mjs", ".png", ".jpg", ".jpeg", ".gif",
               ".svg", ".webp", ".avif", ".ico", ".woff", ".woff2", ".ttf",
               ".otf", ".eot", ".webm", ".mp4"}
MAX_HTML = 2_000_000
MAX_STYLESHEETS = 1500
MAX_STYLE_BYTES = 1_000_000
URL_RE = re.compile(r"url\(\s*(['\"]?)([^)'\"\s]+)\1\s*\)", re.I)
IMPORT_RE = re.compile(r"@import\s+['\"]([^'\"\s]+)['\"]", re.I)


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.references: list[str] = []
        self.external_base = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "base" and values.get("href"):
            base = urlsplit(values["href"])
            if base.scheme or base.netloc or base.path not in ("", "/"):
                self.external_base = True
        for key in ("src", "href", "poster", "data-src"):
            if values.get(key):
                self.references.append(values[key])
        if values.get("srcset"):
            for segment in values["srcset"].split(","):
                bits = segment.strip().split()
                if bits:
                    self.references.append(bits[0])


def reference_to_path(value: str, base: str) -> tuple[str, str | None]:
    """Return (external|ignored|local|unsafe, normalized local relative path)."""
    value = value.strip()
    if not value or value.startswith(("#", "data:", "blob:", "javascript:")):
        return "ignored", None
    parsed = urlsplit(value)
    if parsed.scheme and parsed.scheme.lower() not in ("http", "https"):
        return "ignored", None
    if parsed.netloc and parsed.hostname not in ("zomorodmelal.ir", "www.zomorodmelal.ir"):
        return "external", None
    path = unquote(parsed.path)
    if not path or "\x00" in path or "\\" in path:
        return "ignored" if not path else "unsafe", None
    if not path.startswith("/"):
        path = posixpath.join(posixpath.dirname("/" + base), path)
    components = path.split("/")
    if ".." in components:
        return "unsafe", None
    normalized = posixpath.normpath(path).lstrip("/")
    if not normalized or normalized.startswith("../"):
        return "ignored", None
    if Path(normalized).suffix.lower() not in VISUAL_EXTS:
        return "ignored", None
    return "local", normalized


def tracked(relative: str) -> bool:
    p = Path(relative)
    if len(p.parts) == 1 and p.suffix.lower() in VISUAL_EXTS:
        return True
    return len(p.parts) >= 2 and p.parts[0] in ("assets", "static")


def audit(root: Path) -> dict[str, int]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("UNTRUSTED_ROOT")
    page = root / "index.html"
    if page.is_symlink() or not page.is_file() or page.stat().st_size > MAX_HTML:
        raise ValueError("UNTRUSTED_HTML")
    parser = Links()
    parser.feed(page.read_text(encoding="utf-8"))
    if parser.external_base:
        raise ValueError("UNSAFE_HTML_BASE")
    sources = [("index.html", x) for x in parser.references]
    sheet_count = 0
    for dirname in ("static", "assets"):
        d = root / dirname
        if not d.is_dir() or d.is_symlink():
            raise ValueError("UNTRUSTED_ASSET_ROOT")
        for parent, dirs, files in os.walk(d, followlinks=False):
            if any((Path(parent) / child).is_symlink() for child in dirs):
                raise ValueError("SYMLINK_DIRECTORY")
            for filename in files:
                if Path(filename).suffix.lower() != ".css":
                    continue
                css = Path(parent) / filename
                if css.is_symlink() or not css.is_file() or css.stat().st_size > MAX_STYLE_BYTES:
                    raise ValueError("UNTRUSTED_CSS")
                sheet_count += 1
                if sheet_count > MAX_STYLESHEETS:
                    raise ValueError("CSS_FILE_LIMIT")
                content = css.read_text(encoding="utf-8", errors="replace")
                relative = css.relative_to(root).as_posix()
                sources.extend((relative, m.group(2)) for m in URL_RE.finditer(content))
                sources.extend((relative, m.group(1)) for m in IMPORT_RE.finditer(content))
    local: set[str] = set()
    external = unsafe = 0
    for source, value in sources:
        category, relative = reference_to_path(value, source)
        if category == "local" and relative:
            local.add(relative)
        elif category == "external":
            external += 1
        elif category == "unsafe":
            unsafe += 1
    unprotected = 0
    missing = 0
    for rel in sorted(local):
        p = root / rel
        if not tracked(rel):
            unprotected += 1
        if p.is_symlink() or not p.is_file():
            missing += 1
    return {
        "LOCAL_REFERENCES": len(local),
        "LOCAL_OUTSIDE_PROTECTED_SCOPE": unprotected,
        "LOCAL_MISSING_OR_SYMLINK": missing,
        "UNSAFE_REFERENCE_COUNT": unsafe,
        "EXTERNAL_DEPENDENCY_COUNT": external,
        "CSS_FILES_PARSED": sheet_count,
    }


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("report", "enforce"):
        raise SystemExit(2)
    try:
        stats = audit(PUBLIC)
    except (OSError, ValueError, UnicodeError) as error:
        print("PUBLIC_REFERENCES_AUDIT=" + type(error).__name__, file=sys.stderr)
        raise SystemExit(7) from None
    for key, count in stats.items():
        print("PUBLIC_REFERENCES_" + key + "=" + str(count))
    if sys.argv[1] == "enforce" and (
        stats["LOCAL_OUTSIDE_PROTECTED_SCOPE"]
        or stats["LOCAL_MISSING_OR_SYMLINK"]
        or stats["UNSAFE_REFERENCE_COUNT"]
    ):
        print("PUBLIC_REFERENCES_AUDIT=NOT_FULLY_PROTECTED")
        raise SystemExit(7)
    print("PUBLIC_REFERENCES_AUDIT=READ_ONLY_COMPLETE")


if __name__ == "__main__":
    main()
