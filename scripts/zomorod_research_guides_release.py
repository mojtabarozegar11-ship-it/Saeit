#!/usr/bin/env python3
"""Add-only cPanel publisher for Zomorod Melal's reviewed research guides.

No network, third-party modules, template edits, or existing-file replacement.
Run `plan` first; `apply` requires the exact manifest release ID and live
template SHA-256 printed by plan. A journal permits hash-guarded rollback.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

MARKDOWN_LINE = re.compile(r"^(#{1,3})\s+(.+)$")
UL = re.compile(r"^\s*[-*]\s+(.+)$")
OL = re.compile(r"^\s*\d+[.)]\s+(.+)$")
SAFE_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
RELEASE_PREFIX = "ZM-RESEARCH-GUIDES-"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON_OBJECT_REQUIRED")
    return value


def secure_file(path: Path, root: Path, *, must_exist: bool = True) -> Path:
    """Reject links and escapes for files in a narrowly scoped real root."""
    root = root.resolve(strict=True)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("INVALID_ROOT")
    rel = path.relative_to(root)  # absolute, lexically inside the chosen root
    if not rel.parts or any(part in (".", "..") for part in rel.parts):
        raise ValueError("UNSAFE_PATH")
    parent = root
    for part in rel.parts[:-1]:
        parent = parent / part
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise ValueError("UNSAFE_PARENT " + str(parent))
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError("UNSAFE_TARGET " + str(path))
    if must_exist and not path.is_file():
        raise FileNotFoundError(path)
    return path


def inline(text: str) -> str:
    """Deliberately small, escaped Markdown subset for trusted editorial text."""
    escaped = html.escape(text, quote=True)

    def link(match: re.Match[str]) -> str:
        label, url = match.group(1), html.unescape(match.group(2))
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("ONLY_PUBLIC_HTTPS_LINKS_ALLOWED")
        return '<a href="{}" rel="noopener noreferrer">{}</a>'.format(
            html.escape(url, quote=True), label
        )

    escaped = re.sub(r"\[([^\[\]]+)\]\((https://[^\s)]+)\)", link, escaped)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    return escaped


def markdown_body(raw: str) -> tuple[str, str]:
    """Render headings, paragraphs, horizontal rules and one-level lists."""
    title = ""
    parts: list[str] = []
    paragraph: list[str] = []
    list_kind = ""

    def flush_paragraph() -> None:
        if paragraph:
            parts.append("<p>" + inline(" ".join(paragraph)) + "</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal list_kind
        if list_kind:
            parts.append("</" + list_kind + ">")
            list_kind = ""

    for original in raw.splitlines():
        line = original.strip()
        if not line:
            flush_paragraph()
            close_list()
            continue
        if line == "---":
            flush_paragraph()
            close_list()
            parts.append("<hr>")
            continue
        heading = MARKDOWN_LINE.match(line)
        if heading:
            flush_paragraph()
            close_list()
            level = len(heading.group(1))
            value = heading.group(2).strip()
            if level == 1:
                if title:
                    raise ValueError("MULTIPLE_H1")
                title = value
            parts.append(f"<h{level}>" + inline(value) + f"</h{level}>")
            continue
        bullet = UL.match(line)
        number = OL.match(line)
        if bullet or number:
            flush_paragraph()
            desired = "ul" if bullet else "ol"
            if list_kind != desired:
                close_list()
                list_kind = desired
                parts.append("<" + list_kind + ">")
            parts.append("<li>" + inline((bullet or number).group(1)) + "</li>")
            continue
        close_list()
        paragraph.append(line)
    flush_paragraph()
    close_list()
    if not title or len(parts) < 8:
        raise ValueError("INCOMPLETE_ARTICLE")
    return title, "\n".join(parts)


def template_page(template: str, title: str, article_html: str, canonical: str) -> bytes:
    main = list(re.finditer(r"<main\b[^>]*>[\s\S]*?</main\s*>", template, re.I))
    if len(main) != 1:
        raise ValueError("UNEXPECTED_MAIN_LAYOUT")
    title_tags = list(re.finditer(r"<title\b[^>]*>[\s\S]*?</title\s*>", template, re.I))
    if len(title_tags) != 1 or template.lower().count("</head>") != 1:
        raise ValueError("UNEXPECTED_HEAD_LAYOUT")
    safe_title = html.escape(title, quote=True)
    main_open = re.match(r"<main\b[^>]*>", main[0].group(0), re.I).group(0)
    article = (
        '<article lang="fa" dir="rtl" aria-label="مقاله علمی و آموزشی" '
        'style="max-width:960px;margin:2rem auto;padding:1rem 1.25rem;line-height:1.95">'
        + article_html + "</article>"
    )
    next_page = template[: main[0].start()] + main_open + article + "</main>" + template[main[0].end() :]
    next_page = re.sub(r"<title\b[^>]*>[\s\S]*?</title\s*>",
                       "<title>" + safe_title + " | زمرد ملل</title>", next_page, count=1, flags=re.I)
    # Neutralise inherited research-page canonical; emit exactly one correct URL.
    next_page = re.sub(r"<link\b[^>]*\brel\s*=\s*['\"]canonical['\"][^>]*>",
                       "", next_page, flags=re.I)
    next_page = next_page.replace("</head>",
                                  '<link rel="canonical" href="' + html.escape(canonical, quote=True)
                                  + '">\n</head>', 1)
    return next_page.encode("utf-8")


def load_release(source_root: Path, web_root: Path, manifest_path: Path) -> tuple[dict, str, dict[str, bytes]]:
    source_root = source_root.resolve(strict=True)
    web_root = web_root.resolve(strict=True)
    template_path = secure_file(web_root / "research" / "index.html", web_root)
    template_bytes = template_path.read_bytes()
    template = template_bytes.decode("utf-8")
    manifest = read_json(secure_file(manifest_path, source_root))
    release = manifest.get("release_id", "")
    if not isinstance(release, str) or not release.startswith(RELEASE_PREFIX) or not re.fullmatch(r"[\w-]+", release):
        raise ValueError("INVALID_RELEASE_ID")
    if manifest.get("production_status") != "NOT_DEPLOYED" or manifest.get("site") != "https://zomorodmelal.ir":
        raise ValueError("BAD_MANIFEST_STATUS_OR_SITE")
    guides = manifest.get("guides")
    if not isinstance(guides, list) or not 1 <= len(guides) <= 20:
        raise ValueError("INVALID_GUIDE_COUNT")
    rendered: dict[str, bytes] = {}
    for guide in guides:
        url = guide.get("desired_url", "")
        m = re.fullmatch(r"https://zomorodmelal\.ir/research/guides/([a-z0-9-]+)/", url)
        if not m or not SAFE_SLUG.fullmatch(m.group(1)):
            raise ValueError("INVALID_TARGET_URL " + str(url))
        if guide.get("status") not in ("EDITORIAL_REVIEW_REQUIRED", "APPROVED_FOR_SITE") or guide.get("live_verified") is not False:
            raise ValueError("REVIEW_GATE_NOT_PRESERVED")
        rel = Path(str(guide.get("source_path", "")))
        if rel.is_absolute() or ".." in rel.parts or rel.suffix != ".md":
            raise ValueError("INVALID_SOURCE_PATH")
        source = secure_file(source_root / rel, source_root).read_text(encoding="utf-8")
        title, body = markdown_body(source)
        target = f"research/guides/{m.group(1)}/index.html"
        rendered[target] = template_page(template, title, body, url)
    return manifest, digest(template_bytes), rendered


def preflight(web_root: Path, rendered: dict[str, bytes]) -> None:
    for rel in rendered:
        path = secure_file(web_root / rel, web_root, must_exist=False)
        if path.exists():
            raise FileExistsError("EXISTING_PAGE_NO_OVERWRITE " + rel)


def atomic_new(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def apply_release(web_root: Path, state_root: Path, release: str, expected: str,
                  actual: str, rendered: dict[str, bytes]) -> None:
    if expected != actual:
        raise ValueError("LIVE_TEMPLATE_SHA_MISMATCH")
    live_template = secure_file(web_root / "research" / "index.html", web_root)
    if digest(live_template.read_bytes()) != actual:
        raise ValueError("LIVE_TEMPLATE_CHANGED_AFTER_PLAN")
    preflight(web_root, rendered)
    state_root.mkdir(parents=True, exist_ok=True)
    folder = state_root / release
    folder.mkdir(mode=0o700, exist_ok=False)
    # Persist the exact allowlist *before* creating any public file. If a
    # process dies after its first atomic write, rollback can still identify
    # that file by digest without touching unrelated site content.
    journal = {"release_id": release, "template_sha256": actual,
               "created": {rel: digest(data) for rel, data in rendered.items()},
               "state": "in_progress"}
    (folder / "journal.json").write_text(json.dumps(journal, indent=2), encoding="utf-8")
    try:
        for rel, data in rendered.items():
            target = secure_file(web_root / rel, web_root, must_exist=False)
            target.parent.mkdir(parents=True, exist_ok=True)
            atomic_new(target, data)
        journal["state"] = "installed_unverified"
        (folder / "journal.json").write_text(json.dumps(journal, indent=2), encoding="utf-8")
    except BaseException:
        # Leave the journal and matching created files for an explicit safe rollback.
        (folder / "journal.json").write_text(json.dumps(journal, indent=2), encoding="utf-8")
        raise
    print(json.dumps({"status": "INSTALLED_UNVERIFIED", "count": len(rendered),
                      "release_id": release}, ensure_ascii=False))


def rollback_release(web_root: Path, state_root: Path, release: str) -> None:
    journal_path = state_root / release / "journal.json"
    journal = read_json(journal_path)
    if journal.get("release_id") != release or journal.get("state") not in ("in_progress", "installed_unverified"):
        raise ValueError("INVALID_ROLLBACK_JOURNAL")
    blockers = []
    for rel, expected in journal.get("created", {}).items():
        target = secure_file(web_root / rel, web_root, must_exist=False)
        if target.is_file() and digest(target.read_bytes()) == expected:
            target.unlink()
        elif target.exists():
            blockers.append(rel)
    journal["state"] = "rollback_blocked" if blockers else "rolled_back"
    journal["blockers"] = blockers
    journal_path.write_text(json.dumps(journal, indent=2), encoding="utf-8")
    if blockers:
        raise RuntimeError("CHANGED_FILES_NOT_REMOVED " + ",".join(blockers))
    print(json.dumps({"status": "ROLLED_BACK", "release_id": release}))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "apply", "rollback"))
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--web-root", type=Path, required=True)
    parser.add_argument("--manifest", default="content/zomorod-research-guides/publication-manifest-20261108.json")
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--confirm-release-id")
    parser.add_argument("--expected-template-sha")
    args = parser.parse_args()
    web_root = args.web_root.resolve(strict=True)
    source_root = args.source_root.resolve(strict=True)
    state_root = args.state_root or (web_root.parent / ".backups" / "zomorod-research-guides")
    if args.mode == "rollback":
        if not args.confirm_release_id:
            raise ValueError("EXPLICIT_RELEASE_ID_REQUIRED")
        rollback_release(web_root, state_root, args.confirm_release_id)
        return 0
    manifest, template_sha, rendered = load_release(source_root, web_root, source_root / args.manifest)
    preflight(web_root, rendered)
    if args.mode == "plan":
        print(json.dumps({"status": "PLAN_ONLY", "release_id": manifest["release_id"],
                          "template_sha256": template_sha,
                          "pages": {k: digest(v) for k, v in rendered.items()}},
                         ensure_ascii=False, indent=2))
        return 0
    if args.confirm_release_id != manifest["release_id"] or not args.expected_template_sha:
        raise ValueError("EXPLICIT_CONFIRMATION_AND_TEMPLATE_HASH_REQUIRED")
    if any(g["status"] != "APPROVED_FOR_SITE" for g in manifest["guides"]):
        raise ValueError("EDITORIAL_APPROVAL_REQUIRED_BEFORE_LIVE_WRITE")
    apply_release(web_root, state_root, manifest["release_id"],
                  args.expected_template_sha, template_sha, rendered)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, UnicodeError, KeyError) as exc:
        print(f"RELEASE_ABORTED: {exc}", file=sys.stderr)
        sys.exit(2)
