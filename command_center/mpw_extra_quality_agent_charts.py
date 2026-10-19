"""Evidence-backed private scientific-review and digital-product policy graphs."""
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path

PRIVATE=Path("/home/zomorod2/.private_mojplaywin_main_agents/v91_verified_main_port_20261018/operator_state")
MAX_RECORDS=250
WINDOW=14

def private_dir(path):
    return path.is_dir() and not path.is_symlink() and (path.stat().st_mode & 0o077)==0

def entry(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>20000:return None
    try:
        row=json.loads(path.read_text(encoding="utf-8"))
        return row if isinstance(row,dict) else None
    except (ValueError,UnicodeError,OSError):
        return None

def parsed_date(value):
    if not isinstance(value,str) or len(value)>45:return None
    try:
        stamp=datetime.fromisoformat(value.replace("Z","+00:00"))
        return stamp.astimezone(timezone.utc) if stamp.tzinfo else None
    except ValueError:return None

def extra_review_charts(now=None,state=PRIVATE):
    now=now or datetime.now(timezone.utc)
    days=[(now.date()-timedelta(days=i)).isoformat() for i in reversed(range(WINDOW))]
    if not private_dir(state):
        return []
    defs=(
        ("scientific_quality_v11","ربات کنترل کیفیت علمی","quality_reviews",
         "بازبینی شواهد پژوهشی و استاندارد علمی برگرفته از زمرد ملل"),
        ("product_policy_v91","ربات غربالگری محصول دیجیتال","v91_product_policy_audits",
         "کنترل کیفیت، شواهد ارزش خریدار و قواعد عرضه محصول دیجیتال"),
    )
    result=[]
    for code,title,folder,mission in defs:
        counts={day:0 for day in days}
        blocked=0
        last=None
        state_dir=state/folder
        if private_dir(state_dir):
            for f in list(sorted(state_dir.glob("*.json")))[:MAX_RECORDS]:
                r=entry(f)
                if not r or r.get("tenant")!="mojplaywin-main":continue
                if code=="scientific_quality_v11":
                    status=r.get("status")
                    if status not in ("needs_editorial_revision","review_ready_not_published"):continue
                else:
                    gate=r.get("workbook_gate")
                    if not isinstance(gate,dict) or r.get("auto_publish") is not False or r.get("sale_ready") is not False:
                        continue
                stamp=parsed_date(r.get("reviewed_utc"))
                if stamp is None or stamp>now+timedelta(minutes=5):continue
                key=stamp.date().isoformat()
                if key in counts:
                    blocked+=int(status=="needs_editorial_revision") if code=="scientific_quality_v11" else int(not gate.get("allowed",False))
                    counts[key]+=1
                    if last is None or stamp>last:last=stamp
        series=list(counts.values())
        current=last is not None and timedelta(0)<=now-last<=timedelta(hours=2)
        result.append({
            "id":code,"title":title,"setting":mission,
            "status":"unavailable" if last is None else "active_private" if current else "stale_heartbeat",
            "metric_kind":"private_review_checks",
            "history_available":last is not None,
            "queue":None,"completed":sum(series),"warning_count":blocked,
            "error_count":None,"days":days,"series":series,
            "last_observed_utc":last.isoformat() if last else None,
            "note":("نمودار: تعداد پرونده‌های بازبینی‌شده بر اساس تاریخ آخرین ارزیابی. "
                    "هشدار یعنی نیاز به اصلاح یا تأیید؛ به معنی خطای برنامه نیست."),
        })
    return result
