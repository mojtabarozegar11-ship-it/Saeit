"""Private-content-free structural HTML QA under Mojtaba.bot.ai.

Site-owned Zomorod's former PHP evidence worker checks title, H1,
description and anchors. This adapter preserves those four functional
checks while omitting raw content and storing no evidence database.
Does NOT infer factual accuracy, ownership, indexing, SEO rank or commerce.
"""
from html.parser import HTMLParser


class _Structure(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_title = False
        self.title_parts = []
        self.title_bytes = 0
        self.h1 = 0
        self.description = False
        self.anchors = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        fields = {k.lower(): v for k, v in attrs if k}
        if tag == "title":
            self.in_title = True
        elif tag == "h1":
            self.h1 += 1
        elif tag == "meta" and (fields.get("name") or "").lower() == "description":
            if (fields.get("content") or "").strip():
                self.description = True
        elif tag == "a" and fields.get("href") is not None:
            self.anchors += 1

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)


def assess_html(data: bytes):
    """Exact bounded-input comparison with four original PHP criteria."""
    if type(data) is not bytes or not 64 <= len(data) <= 262144:
        return {"status": "blocked", "score": 0,
                "issues": ["invalid_or_short_html"], "source_content_logged": False}
    try:
        document = data.decode("utf-8", "strict")
        parser = _Structure()
        parser.feed(document)
        parser.close()
    except (UnicodeError, ValueError, TypeError):
        return {"status": "blocked", "score": 0,
                "issues": ["invalid_html_encoding"], "source_content_logged": False}
    title = " ".join("".join(parser.title_parts).split())
    issues = []
    if not title:
        issues.append("missing_title")
    elif len(title) > 100:
        issues.append("title_over_100_chars")
    if parser.h1 != 1:
        issues.append("h1_count_not_one")
    if not parser.description:
        issues.append("missing_meta_description")
    if parser.anchors < 1:
        issues.append("no_anchor_links")
    return {
        "status": "review", "score": max(0, 100 - 25*len(issues)),
        "issues": issues, "title_length": len(title),
        "h1_count": parser.h1, "meta_description_present": parser.description,
        "anchor_candidates": parser.anchors, "source_content_logged": False,
        "external_data_verified": False, "publication_proven": False,
    }
