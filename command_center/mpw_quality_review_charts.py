"""Source-backed 14-day private MojPlayWin research/newsroom quality reviewer metrics."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json
ROOT=Path("/home/zomorod2/.private_mojplaywin_main_agents/v91_verified_main_port_20261018/operator_state/quality_reviews")
def quality_review_chart_rows(now=None,source=ROOT):
    moment=now or datetime.now(timezone.utc)
    days=[(moment.date()-timedelta(days=i)).isoformat() for i in reversed(range(14))]
    result={"id":"editorial_quality","title":"ایجنت کنترل کیفیت پژوهش، خبرنامه و سئو",
            "setting":"ارزیابی کیفیت مستند، اصالت منابع، ساختار سئو و نگه‌داشتن محتوای ناقص برای اصلاح",
            "status":"unavailable","metric_kind":"editorial_quality_reviews",
            "queue":None,"completed":0,"needs_revision":0,"ready_for_human_review":0,
            "days":days,"series":[0]*14,"history_available":False,
            "last_observed_utc":None,"note":"امتیاز کیفیت جایگزین بررسی صحت علمی توسط انسان یا مجوز انتشار نیست."}
    if not source.is_dir() or source.is_symlink() or source.stat().st_mode&0o077:
        return [result]
    counts={d:0 for d in days}
    most_recent=None
    seen=set()
    for file in sorted(source.glob("*.json"))[:300]:
        if not file.is_file() or file.is_symlink() or file.stat().st_size>24000:
            continue
        try:
            entry=json.loads(file.read_text(encoding="utf8"))
        except (ValueError,OSError,UnicodeError):
            continue
        if entry.get("tenant")!="mojplaywin-main" or not entry.get("never_auto_publish") is True:
            continue
        key=entry.get("source_task_digest")
        if not isinstance(key,str) or key in seen:
            continue
        if entry.get("status") not in ("needs_editorial_revision","review_ready_not_published"):
            continue
        try:
            t=datetime.fromisoformat(entry["reviewed_utc"].replace("Z","+00:00"))
            if t.tzinfo is None or t>moment+timedelta(minutes=5):
                continue
            t=t.astimezone(timezone.utc)
        except (ValueError,TypeError,KeyError):
            continue
        seen.add(key)
        day=t.date().isoformat()
        if day not in counts:
            continue
        counts[day]+=1
        result["completed"]+=1
        if entry["status"]=="needs_editorial_revision":
            result["needs_revision"]+=1
        else:
            result["ready_for_human_review"]+=1
        if most_recent is None or t>most_recent:
            most_recent=t
    result["series"]=[counts[x] for x in days]
    if most_recent is not None:
        result["history_available"]=True
        result["last_observed_utc"]=most_recent.isoformat()
        result["status"]="active_private" if timedelta(0)<=moment-most_recent<=timedelta(hours=2) else "stale_heartbeat"
    return [result]
