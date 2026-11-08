"""Mandatory exclusion of political or Israel-related newsroom content.

This is a conservative lexical safety gate, not a semantic fact checker.
All remaining news still requires human editorial review before publication.
"""

from html import unescape
import re
import unicodedata
from urllib.parse import unquote


def _normalize(value: object) -> str:
    text = unquote(unescape(str(value or ""))).casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.translate(str.maketrans({
        "ي": "ی", "ى": "ی", "ك": "ک", "إ": "ا", "أ": "ا", "ٱ": "ا",
        "آ": "ا", "ة": "ه", "ۀ": "ه", "ـ": "", "\u200c": "", "\u200d": "",
    }))
    return text


_ISRAEL = re.compile(
    r"\b(?:israel(?:i|is|ites)?|israels|tel[\s_-]*aviv|jerusalem|zionis\w*|"
    r"gaza|west[\s_-]*bank|knesset|netanyahu|mossad|haifa|"
    r"ben[\s_-]*gurion|ashkelon|sderot|idf)\b"
    r"|اسرا[ئی]?یل|صهیون|تل[\s_-]*اویو|اورشلیم|غزه|"
    r"کرانه[\s_-]*باختری|نتانیاهو|الکنیاست|الکنیست|کنست|موساد|حیفا|"
    r"بن[\s_-]*گوریون|اشکلون|القدس|نتنیاهو"
    r"|ישראל|ישראלי|תל[\s_-]*אביב|ירושלים|עזה|הכנסת|נתניהו|מוסד",
    re.IGNORECASE,
)

_POLITICAL = re.compile(
    r"\b(?:politic\w*|elect(?:ion|oral|ed|ions)\w*|parliament\w*|"
    r"presiden\w*|prime[\s_-]+minister\w*|minister\w*|"
    r"government\w*|governor\w*|senat\w*|congress\w*|"
    r"lawmaker\w*|legislator\w*|foreign[\s_-]*policy|"
    r"white[\s_-]*house|national[\s_-]*security|"
    r"diploma\w*|sanction\w*|ceasefire\w*|militar\w*|"
    r"warfare|war|geopolitic\w*|referendum\w*|coup|"
    r"legislat\w*|ambassador\w*|ballot\w*)\b"
    r"|سیاس|سيا(?:س|ست)|انتخابات|انتخاباتی|پارلمان|مجلس|ریاست[\s_-]*جمهور|"
    r"رئیس[\s_-]*جمهور|رییس[\s_-]*جمهور|نخست[\s_-]*وزیر|"
    r"وزیر|وزارت|دولت|حکومت|دیپلما|تحریم|(?<![\u0600-\u06ff])جنگ(?![\u0600-\u06ff])|نظامی|"
    r"آتش[\s_-]*بس|کابینه|سفیر|کودتا|رفراندوم|"
    r"حكوم|انتخابات|وزراء|برلمان|استاندار|فرماندار|کاخ[\s_-]*سفید|"
    r"الانتخاب|الرئیس|الرییس|الوزیر|الحکومه|الجیش|"
    r"ממשלה|בחירות|פוליטיק|כנסת",
    re.IGNORECASE,
)


def blocked_news_reason(*texts: object) -> str | None:
    """Identify clearly prohibited content; ambiguous news must be editor-reviewed.

    Inspect title, summary, full body, keywords and source metadata together.
    This function does not approve or certify content that returns None.
    """
    normalized = "\n".join(_normalize(t) for t in texts)
    if _ISRAEL.search(normalized):
        return "israel_related"
    if _POLITICAL.search(normalized):
        return "political_news"
    return None


def blocked_story_reason(story) -> str | None:
    """Apply the same exclusion to legacy records without changing the database."""
    source = getattr(story, "source", None)
    return blocked_news_reason(
        getattr(story, "title", ""),
        getattr(story, "summary", ""),
        getattr(story, "body", ""),
        getattr(story, "seo_keywords", []),
        getattr(source, "title", ""),
        getattr(source, "publisher", ""),
        getattr(source, "url", ""),
        getattr(story, "company_activity_content", ""),
        getattr(story, "company_unit_title", ""),
        getattr(story, "company_project_title", ""),
    )


def visible_story_links(links) -> list:
    """Remove links to prohibited news, including legacy company links."""
    return [link for link in links if not (
        getattr(link, "newsletter_story", None) and blocked_story_reason(link.newsletter_story)
    )]


def visible_news_stories(queryset, *, limit: int) -> list:
    """Fail closed on legacy forbidden stories across public archives.

    Only inspect a bounded selection to avoid unbounded page work. If all
    inspected records are blocked, an empty list is safer than exposing one.
    """
    visible = []
    for story in queryset.select_related("source")[: max(100, limit * 10)]:
        if not blocked_story_reason(story):
            visible.append(story)
            if len(visible) == limit:
                break
    return visible
