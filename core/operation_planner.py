"""Strict, deterministic chat-intent parser for the sole mojtaba.bot.ai bot.

The model cannot initiate an action. Explicit, unambiguous, one-line owner
requests may become PENDING requests with their target and arguments bound.
An intent is not an owner approval, execution receipt, or sales outcome.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ChatOperation:
    operation_id: str
    action: str
    target: str
    parameters: dict[str, Any]
    risk: str
    approval_required: bool = True


# No URL, traversal, percent-encoded path, query string, backslash, unicode
# confusable or ambiguous root routes may be used to create/edit a page.
DRAFT_PATH = re.compile(r"/[A-Za-z0-9_./-]{1,179}\Z")
PATH_TOKEN = re.compile(
    r"(?<![A-Za-z0-9:/])(/[A-Za-z0-9_./%?#\\~-]+)(?=$|[\s«»“”\"'])"
)
QUOTES = (
    re.compile(r"«([^«»]{1,300})»"),
    re.compile(r"“([^“”]{1,300})”"),
    re.compile(r'"([^"]{1,300})"'),
)
START_CREATE = re.compile(
    r"^(?:لطفاً?\s+|please\s+)?(?:صفحه جدید|صفحه تازه|صفحه اضافه|create page|add page)\s+",
    re.IGNORECASE,
)
START_EDIT = re.compile(
    r"^(?:لطفاً?\s+|please\s+)?(?:محتوای صفحه|ویرایش صفحه|update page|edit page)\s+",
    re.IGNORECASE,
)
ANY_MUTATION_VERB = re.compile(
    r"(?:صفحه جدید|صفحه تازه|صفحه اضافه|create page|add page|"
    r"محتوای صفحه|ویرایش صفحه|update page|edit page)",
    re.IGNORECASE,
)
ZOMOROD = re.compile(r"(?:\bzomorodmelal(?:\.ir)?\b|سایت\s+زمرد(?:\s+ملل)?)", re.IGNORECASE)
MOJPLAYWIN = re.compile(r"(?:\bmojplaywin(?:\.com)?\b|سایت\s+مج\s*پلی\s*وین)", re.IGNORECASE)
NEGATION = re.compile(
    r"(?:\b(?:do not|don't|dont|never|cancel|without|not now)\b|"
    r"(?:اجرا\s*نکن|انجام\s*نده|نساز|نکن|لغو\s*کن|ویرایش\s*نکن|"
    r"لطفا\s*نه|لطفاً\s*نه))",
    re.IGNORECASE,
)
INVISIBLE = re.compile(r"[\x00-\x1f\x7f\u200b\u202a-\u202e\u2066-\u2069\ufeff]")
PREFLIGHT = frozenset((
    "cpanel preflight", "cpanel preflight now", "preflight cpanel",
    "run cpanel preflight", "execute cpanel preflight",
    "پیش‌بررسی cpanel", "پیش‌بررسی cpanel را اجرا کن",
    "پیش‌بررسی cpanel را انجام بده",
))
PASSENGER = frozenset((
    "passenger inventory", "passenger inventory now", "run passenger inventory",
    "فهرست passenger", "فهرست passenger را نمایش بده",
    "مسیرهای passenger", "مسیرهای passenger را نمایش بده",
))
DEPLOY = re.compile(
    r"(?:انتشار نسخه|deploy release|انتشار سایت|deploy سایت)\s+"
    r"(?:را\s+)?(?:انجام بده|اجرا کن|اکنون|الان|now)\Z",
    re.IGNORECASE,
)
SPEC = {
    "cpanel.preflight": ("cPanel", "medium", frozenset()),
    "cpanel.passenger_inventory": ("cPanel", "medium", frozenset()),
    "cpanel.deploy_release": ("cPanel", "critical", frozenset()),
    "site.create_draft_page": ("site", "high", frozenset(("path", "title", "body"))),
    "site.update_draft_page": ("site", "high", frozenset(("path", "instruction"))),
}


def valid_draft_path(path: object, target: object) -> bool:
    """Canonical path contract shared with the Django approval validator."""
    if type(target) is not str or target not in {"mojplaywin", "zomorodmelal"}:
        return False
    if type(path) is not str or DRAFT_PATH.fullmatch(path) is None:
        return False
    if path == "/" or "//" in path or path.endswith("/.") or path.endswith("/.."):
        return False
    if any(part in {".", ".."} for part in path.split("/")):
        return False
    if target == "zomorodmelal" and not path.startswith("/company/"):
        return False
    return True


def _unquoted_text(raw: str) -> tuple[str, list[str]]:
    titles: list[str] = []
    without = raw
    for pattern in QUOTES:
        def remove(match: re.Match[str]) -> str:
            titles.append(match.group(1))
            return " "
        without = pattern.sub(remove, without)
    return without, titles


def _explicit_target(unquoted: str) -> str | None:
    domestic = ZOMOROD.search(unquoted) is not None
    international = MOJPLAYWIN.search(unquoted) is not None
    if domestic == international:
        return None  # both or neither: never infer a default site
    return "zomorodmelal" if domestic else "mojplaywin"


def _one_path(unquoted: str, target: str) -> str | None:
    paths = PATH_TOKEN.findall(unquoted)
    if len(paths) != 1:
        return None
    path = paths[0]
    return path if valid_draft_path(path, target) else None


def plan_chat_operation(text: str) -> ChatOperation | None:
    """Parse a single explicit user instruction, never discussion or quotes."""
    if type(text) is not str:
        return None
    raw = text.strip()
    if not raw or len(raw) > 4000 or INVISIBLE.search(raw):
        return None
    unquoted, titles = _unquoted_text(raw)
    # Questions, negated requests and mixed operations cannot become executable.
    if "؟" in unquoted or "?" in unquoted or NEGATION.search(unquoted):
        return None
    low = re.sub(r"\s+", " ", unquoted).strip().casefold()
    canonical_command = low.strip(" .!،؛")

    if canonical_command in PREFLIGHT:
        return ChatOperation(uuid.uuid4().hex, "cpanel.preflight", "cPanel", {}, "medium")
    if canonical_command in PASSENGER:
        return ChatOperation(uuid.uuid4().hex, "cpanel.passenger_inventory", "cPanel", {}, "medium")
    if DEPLOY.fullmatch(canonical_command):
        return ChatOperation(uuid.uuid4().hex, "cpanel.deploy_release", "cPanel", {}, "critical")

    create, edit = bool(START_CREATE.match(low)), bool(START_EDIT.match(low))
    if not (create ^ edit) or len(ANY_MUTATION_VERB.findall(low)) != 1:
        return None
    target = _explicit_target(low)
    if target is None:
        return None
    path = _one_path(unquoted, target)
    if path is None:
        return None
    if create:
        if len(titles) != 1:
            return None
        title = titles[0].strip()
        if not title or len(title) > 200 or "<" in title or ">" in title:
            return None
        return ChatOperation(
            uuid.uuid4().hex, "site.create_draft_page", target,
            {"path": path, "title": title, "body": raw}, "high",
        )
    if titles:
        # A quoted instruction can resemble a second operator's intent.
        # Use only the explicit, already bounded request text for the draft.
        if len(titles) > 1:
            return None
    return ChatOperation(
        uuid.uuid4().hex, "site.update_draft_page", target,
        {"path": path, "instruction": raw}, "high",
    )


def approval_reason(operation: ChatOperation, *, session_id: int | None = None) -> str:
    """Produce a bound, typed pending-approval reason; never consume authority."""
    if not isinstance(operation, ChatOperation) or operation.approval_required is not True:
        raise ValueError("A typed, approval-required operation is mandatory")
    if type(operation.operation_id) is not str or re.fullmatch(
        r"[0-9a-f]{32}", operation.operation_id
    ) is None:
        raise ValueError("Invalid immutable operation identifier")
    spec = SPEC.get(operation.action) if type(operation.action) is str else None
    if spec is None or operation.risk != spec[1]:
        raise ValueError("Unknown action or risk")
    if type(operation.target) is not str:
        raise ValueError("Target must be a string")
    if spec[0] == "cPanel":
        if operation.target != "cPanel":
            raise ValueError("Mismatched cPanel target")
    elif operation.target not in {"mojplaywin", "zomorodmelal"}:
        raise ValueError("Unknown site target")
    if type(operation.parameters) is not dict or set(operation.parameters) != spec[2]:
        raise ValueError("Invalid action parameters")
    if spec[0] == "site":
        if not valid_draft_path(operation.parameters["path"], operation.target):
            raise ValueError("Invalid draft path or target")
        key = "title" if operation.action == "site.create_draft_page" else "instruction"
        if type(operation.parameters[key]) is not str or not operation.parameters[key].strip():
            raise ValueError("Empty draft title/instruction")
        if len(operation.parameters[key]) > (200 if key == "title" else 4000):
            raise ValueError("Draft value exceeds bound")
        if key == "title":
            body = operation.parameters["body"]
            if type(body) is not str or not body or len(body) > 4000:
                raise ValueError("Invalid draft body")
    if type(session_id) is not int or session_id <= 0:
        raise ValueError("A real, positive chat session is required")
    return json.dumps({
        "operation_id": operation.operation_id,
        "action": operation.action,
        "target": operation.target,
        "parameters": operation.parameters,
        "session_id": session_id,
    }, ensure_ascii=False, sort_keys=True)
