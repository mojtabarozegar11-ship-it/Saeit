"""Evidence-first global social research: no fabricated metrics or unauthorized scraping."""
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

PLATFORMS = {"instagram", "facebook", "youtube", "tiktok", "threads", "pinterest", "x", "linkedin", "reddit"}
def evaluate(items, as_of=None):
    as_of = as_of or datetime.now(timezone.utc)
    ranked = []
    for item in items:
        try:
            url = item["url"]
            u = urlparse(url)
            if u.scheme != "https" or not u.hostname or u.username or u.password:
                continue
            platform = item["platform"].lower()
            if platform not in PLATFORMS:
                continue
            views = item.get("views")
            likes = item.get("likes")
            comments = item.get("comments")
            shares = item.get("shares")
            followers = item.get("followers")
            published = datetime.fromisoformat(item["published_at"].replace("Z", "+00:00"))
            if published.tzinfo is None or published > as_of:
                continue
            values = (views, likes, comments, shares, followers)
            if any(v is not None and (not isinstance(v, int) or isinstance(v, bool) or v < 0) for v in values):
                continue
            if not item.get("source_url") or urlparse(item["source_url"]).scheme != "https":
                continue
            engagement = sum(v or 0 for v in (likes, comments, shares))
            if not views and not followers:
                continue
            rate = engagement / max(1, views or followers)
            days = max(1, (as_of - published).total_seconds() / 86400)
            ranked.append({"platform": platform, "url": url, "source_url": item["source_url"],
                           "published_at": published.isoformat(), "engagement": engagement,
                           "engagement_rate_proxy": round(rate, 5),
                           "velocity_proxy": round(engagement / days, 2),
                           "metrics_basis": "views" if views else "followers",
                           "limitations": "Public engagement proxy; not sales or verified reach"})
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    return sorted(ranked, key=lambda r: (r["engagement_rate_proxy"], r["velocity_proxy"]), reverse=True)

def main():
    root = Path(__file__).resolve().parent
    path = root / "research_sources.json"
    items = json.loads(path.read_text(encoding="utf-8"))["posts"]
    discovery = root / "output" / "youtube_discovery.json"
    if discovery.exists():
        fetched = json.loads(discovery.read_text(encoding="utf-8"))
        if fetched.get("state", {}).get("status") in ("ok", "partial"):
            items.extend(fetched.get("posts", []))
    ranked = evaluate(items)
    out = root / "output"
    out.mkdir(exist_ok=True)
    (out / "research_report.json").write_text(json.dumps({
      "generated_at": datetime.now(timezone.utc).isoformat(),
      "verified_global_ranking": False,
      "posts_evaluated": len(items), "eligible_posts": len(ranked),
      "note": "No live global discovery provider configured. Empty output means no verified evidence, not no trends.",
      "ranked": ranked
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Research evidence evaluated: {len(items)}; eligible: {len(ranked)}; no fabricated global trends")

if __name__ == "__main__":
    main()
