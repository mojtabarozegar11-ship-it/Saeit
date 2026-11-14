"""Moj Prop: localized presentation model sourced from the sole policy engine.

A marketing/read-only division of MojPlayWin; there is deliberately no checkout,
customer registration, brokerage order or wallet call in this module.
"""
import json
from functools import lru_cache
from pathlib import Path

from .rules import LEVELS, POLICY

EXPECTED_GROUPS = {
    "nav": 4, "hero": 7, "stats": 4, "steps": 5,
    "ladder": 4, "rules": 11, "faq": 5, "footer": 2,
}
SUPPORTED_CODES = (
    "en", "fa", "ar", "de", "fr", "es", "pt", "it", "tr", "ru",
    "zh", "ja", "ko", "hi", "id", "vi", "th", "nl", "pl", "ur",
)


@lru_cache(maxsize=1)
def catalog():
    path = Path(__file__).with_name("moj_prop_locales.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "moj-prop.i18n.v1" or data.get("default") != "en":
        raise ValueError("Unexpected Moj Prop translation catalog")
    locales = data.get("locales")
    if not isinstance(locales, dict) or set(locales) != set(SUPPORTED_CODES):
        raise ValueError("Moj Prop requires exactly 20 complete locales")
    for code, item in locales.items():
        if item.get("dir") not in {"ltr", "rtl"} or not item.get("name"):
            raise ValueError(f"Invalid language metadata: {code}")
        if (item["dir"] == "rtl") != (code in {"fa", "ar", "ur"}):
            raise ValueError(f"Invalid language direction: {code}")
        for group, length in EXPECTED_GROUPS.items():
            texts = item.get(group)
            if not isinstance(texts, list) or len(texts) != length:
                raise ValueError(f"Missing or incomplete translation: {code}/{group}")
            if any(not isinstance(v, str) or not v.strip() for v in texts):
                raise ValueError(f"Empty localized text: {code}/{group}")
        social = item.get("social")
        if (not isinstance(social, dict) or set(social) != {"title", "body", "disclosure"}
                or any(not isinstance(v, str) or not v.strip() for v in social.values())):
            raise ValueError(f"Missing complete social rule localization: {code}")
    return locales


def page_context(code="en"):
    """Build safe template-only context. Unsupported codes must be 404 at view."""
    if code not in SUPPORTED_CODES:
        raise ValueError("Unsupported language")
    translations = catalog()
    t = translations[code]
    p = POLICY
    rates = (
        f"{p.phase_one_goal_pct}%",
        f"{p.phase_two_goal_pct}%",
        f"{p.max_daily_loss_pct}%",
        f"{p.max_total_loss_pct}%",
        str(p.min_challenge_days),
        f"{p.best_day_share_pct}%",
        f"{p.order_risk_pct}%",
        f"{p.aggregate_risk_pct}%",
        f"{p.promotion_goal_pct}%",
        str(p.promotion_min_days),
    )
    level_items = [
        {
            "month": n,
            "capital": "$" + f"{int(capital):,}",
            "capital_number": int(capital),
            "bar": f"{max(1, int(capital * 100 / LEVELS[-1]))}%",
        }
        for n, capital in enumerate(LEVELS, 1)
    ]
    paths = [
        {"code": item, "name": translations[item]["name"],
         "url": "/moj-prop/" if item == "en" else f"/moj-prop/{item}/",
         "active": item == code}
        for item in SUPPORTED_CODES
    ]
    return {
        "brand": "Moj Prop",
        "parent_brand": "MojPlayWin",
        "bot_id": p.canonical_bot,
        "code": code,
        "direction": t["dir"],
        "lang_name": t["name"],
        "locale_links": paths,
        "hero": t["hero"],
        "nav": t["nav"],
        "stats": t["stats"],
        "steps": t["steps"],
        "ladder": t["ladder"],
        "rule_title": t["rules"][0],
        "rules": [{"label": key, "value": val}
                  for key, val in zip(t["rules"][1:], rates)],
        "faq": t["faq"],
        "footer": t["footer"],
        "social": t["social"],
        "social_posts_per_platform_per_challenge": p.social_posts_per_platform_per_challenge,
        "challenge_days": p.completion_deadline_days,
        "social_platforms": p.social_posting_platforms,
        "levels": level_items,
        "entry": f"{p.entry_trx} TRX",
        "share": f"{p.trader_profit_share_pct}%",
        "range": "$" + f"{int(LEVELS[0]):,}" + " — $" + f"{int(LEVELS[-1]):,}",
        "phase_count": 2,
        "policy_version": p.version,
        "canonical_url": paths[SUPPORTED_CODES.index(code)]["url"],
    }
