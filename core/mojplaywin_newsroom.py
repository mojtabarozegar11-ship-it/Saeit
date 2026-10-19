"""Independent MojPlayWin newsroom, adapted from Zomorod's evidence-first editorial gate.

No core NewsletterStory models, shared database, company identity or outbound
publishing are used. The SQLite file belongs in private application storage.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

MIN_SCORE = 90
DOMAINS = {"mojplaywin.com", "www.mojplaywin.com"}
CATEGORIES = {"ai", "games", "technology", "digital-commerce", "research", "education", "web3", "business"}
STATES = {"draft", "approved", "published", "rejected"}


def is_mojplaywin(host: str) -> bool:
    return host.split(":", 1)[0].lower().rstrip(".") in DOMAINS


def fingerprint(*values: str) -> str:
    value = "|".join(re.sub(r"\s+", " ", str(x or "")).strip().casefold() for x in values)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def is_https_source(value: str) -> bool:
    try:
        p = urlsplit(value)
        return p.scheme == "https" and bool(p.hostname) and not p.username and not p.password
    except ValueError:
        return False


def quality_score(article: dict) -> tuple[int, dict]:
    """Adapt Zomorod's 100-point criteria to MojPlayWin subjects and authorship."""
    title = str(article.get("title") or "").strip()
    summary = str(article.get("summary") or "").strip()
    body = str(article.get("body") or "").strip()
    analysis = str(article.get("analysis") or "").strip()
    keywords = article.get("keywords") or []
    if not isinstance(keywords, list):
        keywords = []
    source_url = str(article.get("source_url") or "").strip()
    publisher = str(article.get("publisher") or "").strip()
    source_title = str(article.get("source_title") or "").strip()
    internal = article.get("origin") == "internal"
    evidence = str(article.get("evidence") or "").strip()
    checks = {
        "descriptive_title": (35 <= len(title) <= 220, 8),
        "useful_summary": (len(summary) >= 180, 10),
        "substantive_body": (len(body) >= 1200, 18),
        "context_implications": (any(t in body.casefold() for t in (
            "context", "impact", "implication", "risk", "outlook", "زمینه", "پیامد", "اثر")), 8),
        "data_evidence": (bool(re.search(r"\d", body)) or any(
            t in body.casefold() for t in ("study", "data", "report", "research", "آمار", "داده")), 8),
        "independent_analysis": (len(analysis) >= 200, 15),
        "substantive_analysis": (len(analysis) >= 450, 10),
        "seo_keywords": (len({str(x).strip().casefold() for x in keywords if str(x).strip()}) >= 3, 5),
        "event_date": (bool(article.get("event_date")), 4),
        "source_evidence": (bool(evidence) and (internal or (
            is_https_source(source_url) and bool(publisher and source_title))), 10),
        "traceable_origin": (len(evidence) >= 30, 4),
    }
    return sum(weight for passes, weight in checks.values() if passes), {
        key: passes for key, (passes, weight) in checks.items()
    }


def private_db_path() -> Path:
    from django.conf import settings
    supplied = os.getenv("MOJPLAYWIN_NEWSLETTER_DB", "")
    path = Path(supplied) if supplied else Path(settings.BASE_DIR) / ".private" / "mojplaywin-newsletter.sqlite3"
    if not path.is_absolute():
        raise ValueError("Newsletter database path must be absolute")
    path = path.resolve()
    text = str(path).lower()
    if any(t in path.parts for t in ("public_html", "mojplaywin.com", "static", "media")):
        raise ValueError("Newsletter database must not be in a public directory")
    return path


class Newsroom:
    def __init__(self, db_path: Path):
        self.path = Path(db_path).resolve()
        if not self.path.is_absolute() or self.path.suffix != ".sqlite3":
            raise ValueError("Expected an absolute private .sqlite3 file")
        if any(t in self.path.parts for t in ("public_html", "mojplaywin.com", "static", "media")):
            raise ValueError("Refusing to open database in a public directory")

    def _connect(self, write=False):
        if not write and not self.path.exists():
            return None
        if write:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(self.path.parent, 0o700)
        conn = sqlite3.connect(str(self.path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000")
        if write:
            conn.execute("""CREATE TABLE IF NOT EXISTS stories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint TEXT NOT NULL UNIQUE, slug TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL, summary TEXT NOT NULL, body TEXT NOT NULL,
                analysis TEXT NOT NULL, category TEXT NOT NULL,
                source_url TEXT NOT NULL, publisher TEXT NOT NULL,
                source_title TEXT NOT NULL, origin TEXT NOT NULL,
                evidence TEXT NOT NULL, keywords TEXT NOT NULL,
                event_date TEXT NOT NULL, score INTEGER NOT NULL,
                checks TEXT NOT NULL, status TEXT NOT NULL,
                scheduled_at TEXT NOT NULL DEFAULT '',
                published_at TEXT NOT NULL DEFAULT '',
                approved_by TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )""")
            os.chmod(self.path, 0o600)
        return conn

    def create_draft(self, article: dict) -> tuple[int, int]:
        if not isinstance(article, dict):
            raise ValueError("Expected an article object")
        category = str(article.get("category") or "")
        if category not in CATEGORIES:
            raise ValueError("Unknown MojPlayWin newsletter category")
        origin = article.get("origin")
        if origin not in ("internal", "external"):
            raise ValueError("Origin must be internal or external")
        if origin == "external" and not (
            is_https_source(str(article.get("source_url") or "")) and
            article.get("publisher") and article.get("source_title")
        ):
            raise ValueError("External reporting requires attributable HTTPS source")
        title = str(article.get("title") or "").strip()
        summary = str(article.get("summary") or "").strip()
        body = str(article.get("body") or "").strip()
        analysis = str(article.get("analysis") or "").strip()
        if not title or not body:
            raise ValueError("Empty title/body")
        score, checks = quality_score(article)
        fp = fingerprint(category, title, str(article.get("source_url") or ""), str(article.get("event_date") or ""))
        slug = "mpw-" + fp[:24]
        now = datetime.now(timezone.utc).isoformat()
        conn = self._connect(write=True)
        try:
            with conn:
                cursor = conn.execute("""INSERT INTO stories
                (fingerprint,slug,title,summary,body,analysis,category,source_url,
                 publisher,source_title,origin,evidence,keywords,event_date,score,
                 checks,status,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (fp, slug, title, summary, body, analysis, category,
                 str(article.get("source_url") or ""), str(article.get("publisher") or ""),
                 str(article.get("source_title") or ""), origin,
                 str(article.get("evidence") or ""),
                 json.dumps(article.get("keywords") or [], ensure_ascii=False),
                 str(article.get("event_date") or ""), score, json.dumps(checks),
                 "draft", now))
            return cursor.lastrowid, score
        finally:
            conn.close()

    def approve(self, story_id: int, editor: str, when: str = "") -> bool:
        if not editor.strip():
            raise ValueError("Editor identity is mandatory")
        if when:
            dt = datetime.fromisoformat(when.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                raise ValueError("Schedule timestamp must include timezone")
            when = dt.astimezone(timezone.utc).isoformat()
        conn = self._connect(write=True)
        try:
            with conn:
                cur = conn.execute("""UPDATE stories SET status='approved',approved_by=?,scheduled_at=?
                     WHERE id=? AND status='draft' AND score>=?""",
                                   (editor.strip(), when, int(story_id), MIN_SCORE))
            return cur.rowcount == 1
        finally:
            conn.close()

    def publish_due(self, now: str | None = None) -> int:
        now_dt = datetime.fromisoformat(now.replace("Z", "+00:00")) if now else datetime.now(timezone.utc)
        if now_dt.tzinfo is None:
            raise ValueError("now must be timezone aware")
        iso = now_dt.astimezone(timezone.utc).isoformat()
        conn = self._connect(write=True)
        try:
            with conn:
                cur = conn.execute("""UPDATE stories SET status='published',published_at=?
                      WHERE status='approved' AND approved_by<>'' AND score>=?
                      AND (scheduled_at='' OR scheduled_at<=?)""", (iso, MIN_SCORE, iso))
            return cur.rowcount
        finally:
            conn.close()

    def list_published(self, category="", limit=50):
        conn = self._connect()
        if conn is None:
            return []
        try:
            if category and category in CATEGORIES:
                rows = conn.execute("""SELECT * FROM stories WHERE status='published'
                     AND category=? ORDER BY published_at DESC LIMIT ?""", (category, limit))
            else:
                rows = conn.execute("""SELECT * FROM stories WHERE status='published'
                     ORDER BY published_at DESC LIMIT ?""", (limit,))
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_published(self, slug):
        conn = self._connect()
        if conn is None:
            return None
        try:
            row = conn.execute("""SELECT * FROM stories WHERE slug=? AND status='published'""",
                               (slug,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def stats(self):
        conn = self._connect()
        if conn is None:
            return {"draft": 0, "approved": 0, "published": 0, "rejected": 0, "blocked": 0}
        try:
            counts = {state: 0 for state in STATES}
            counts["blocked"] = 0
            for row in conn.execute("SELECT status,COUNT(*) AS n FROM stories GROUP BY status"):
                counts[row["status"]] = row["n"]
            counts["blocked"] = conn.execute(
                "SELECT COUNT(*) FROM stories WHERE status='draft' AND score<?", (MIN_SCORE,)
            ).fetchone()[0]
            return counts
        finally:
            conn.close()
