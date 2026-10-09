"""Fetch region-specific popular YouTube videos using the official API.
Requires YOUTUBE_API_KEY secret. Never scrapes or fabricates statistics.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REGIONS = ("US", "CA", "GB", "IN", "BR", "JP", "DE", "AE")
BASE = "https://www.googleapis.com/youtube/v3/videos"
def normalize(data, region, observed_at):
    posts = []
    for item in data.get("items", []):
        vid = item.get("id")
        snip = item.get("snippet", {})
        stats = item.get("statistics", {})
        if not isinstance(vid, str) or not vid or not snip.get("publishedAt"):
            continue
        def metric(name):
            value = stats.get(name)
            return int(value) if isinstance(value, str) and value.isdecimal() else None
        url = "https://www.youtube.com/watch?v=" + vid
        posts.append({"platform":"youtube","url":url,"source_url":url,
          "published_at":snip["publishedAt"],"observed_at":observed_at,
          "region":region,"title":snip.get("title",""),
          "channel_id":snip.get("channelId",""),
          "views":metric("viewCount"),"likes":metric("likeCount"),
          "comments":metric("commentCount"),"shares":None,
          "collection_method":"official_youtube_mostPopular_chart",
          "ranking_scope":"region-specific YouTube chart, not global all-platform ranking"})
    return posts

def collect(key, regions=REGIONS, opener=urlopen):
    if not key:
        return [], {"status":"not_configured","reason":"YOUTUBE_API_KEY missing"}
    now = datetime.now(timezone.utc).isoformat()
    results, errors = [], []
    for region in regions:
        query = urlencode({"part":"snippet,statistics","chart":"mostPopular",
                           "regionCode":region,"maxResults":25,"key":key})
        request = Request(BASE+"?"+query,headers={"Accept":"application/json"})
        try:
            with opener(request, timeout=15) as response:
                results.extend(normalize(json.load(response),region,now))
        except Exception as exc:
            errors.append({"region":region,"error":type(exc).__name__})
    unique = {}
    for post in results:
        key = post["url"]
        if key not in unique:
            unique[key] = dict(post, regions=[post["region"]])
        elif post["region"] not in unique[key]["regions"]:
            unique[key]["regions"].append(post["region"])
    return list(unique.values()), {"status":"partial" if errors else "ok","regions":list(regions),"errors":errors}

def main():
    root=Path(__file__).resolve().parent
    posts, state=collect(os.getenv("YOUTUBE_API_KEY",""))
    output=root/"output"
    output.mkdir(exist_ok=True)
    (output/"youtube_discovery.json").write_text(json.dumps({"state":state,"posts":posts},
      ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"YouTube discovery: {state['status']}; {len(posts)} posts; no posting")
if __name__=="__main__":
    main()
