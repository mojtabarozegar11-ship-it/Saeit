"""Source-backed chart for the hourly Zomorod-inspired quality reviewer.

No database, Zomorod site reads, cross-tenant paths or inferred success.
"""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json

ROOT=Path("/home/zomorod2/.private_mojplaywin_main_agents/v91_verified_main_port_20261018/operator_state/quality_reviews")

def chart(now=None,root=ROOT):
    now=now or datetime.now(timezone.utc)
    days=[(now.date()-timedelta(days=n)).isoformat() for n in reversed(range(14))]
    counts={day:0 for day in days}
    requires_revision=0
    last=None
    if root.is_dir() and not root.is_symlink() and not root.stat().st_mode&0o077:
        for p in sorted(root.glob("*.json"))[:350]:
            if not p.is_file() or p.is_symlink() or p.stat().st_size>35000:continue
            try:
                obj=json.loads(p.read_text(encoding="utf8"))
                if obj.get("tenant")!="mojplaywin-main":continue
                if obj.get("status") not in ("review_ready_not_published","needs_editorial_revision"):continue
                stamp=datetime.fromisoformat(str(obj["reviewed_utc"]).replace("Z","+00:00"))
                if stamp.tzinfo is None or stamp>now+timedelta(minutes=5):continue
            except (ValueError,KeyError,TypeError,OSError,UnicodeError):continue
            day=stamp.astimezone(timezone.utc).date().isoformat()
            if day in counts:
                counts[day]+=1
                if obj["status"]=="needs_editorial_revision":requires_revision+=1
            if last is None or stamp>last:last=stamp
    fresh=last is not None and timedelta(0)<=now-last<=timedelta(hours=2)
    row={
        "id":"zomorod_quality_reviewer",
        "title":"ایجنت کنترل کیفیت علمی و محتوایی",
        "setting":"بازبینی خصوصی پیش‌نویس‌ها طبق معیارهای علمی و خبرنامه زمرد ملل، بدون انتشار",
        "status":"active_private" if fresh else "stale_heartbeat" if last else "unavailable",
        "days":days,"series":[counts[d] for d in days],
        "history_available":last is not None,"metric_kind":"content_quality_review",
        "queue":None,"completed":None,
        "last_observed_utc":last.isoformat() if last else None,
        "needs_revision_count":requires_revision,
        "note":"نمودار تعداد پیش‌نویس‌های واقعاً بازبینی‌شده در هر روز را نشان می‌دهد. "
               "تعداد نیازمند اصلاح: "+str(requires_revision)+". انتشار خودکار غیرفعال است."
    }
    return row
