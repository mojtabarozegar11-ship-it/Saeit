"""Read-only MojPlayWin private V91 agent metrics for the STAFF dashboard.

Records are read only from the dedicated private MojPlayWin worker state.
No DB, network, shell, factory, Zomorod or child-site reads. The controller's
single heartbeat is NOT passed off as 14 days of master-agent history.
"""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from django.conf import settings

PRIVATE_STATE=Path(
    getattr(settings,"MPW_V91_PRIVATE_OPERATOR_STATE",
            "/home/zomorod2/.private_mojplaywin_main_agents/"
            "v91_verified_main_port_20261018/operator_state")
)
MAX_FILES=1200
MAX_FILE_BYTES=24000
MAX_DAYS=14

def safe_dir(path):
    return path.is_dir() and not path.is_symlink() and path.stat().st_mode & 0o077 == 0

def read_record(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_FILE_BYTES:
        return None
    try:
        value=json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value,dict) else None
    except (OSError,UnicodeError,ValueError):
        return None

def kind_of(record):
    if record.get("tenant")!="mojplaywin-main" or record.get("review_only") is not True:
        return None
    kind=record.get("kind","research_digest")
    return kind if kind in ("research_digest","product_blueprint") else None

def date_of(record):
    value=record.get("generated_utc")
    if not isinstance(value,str) or len(value)>40:
        return None
    try:
        moment=datetime.fromisoformat(value.replace("Z","+00:00"))
        return moment.astimezone(timezone.utc).date() if moment.tzinfo else None
    except ValueError:
        return None

def count_private_runs(state, today):
    dates=[today-timedelta(days=n) for n in reversed(range(MAX_DAYS))]
    days=[d.isoformat() for d in dates]
    period=set(days)
    samples={kind:{day:0 for day in days} for kind in ("research_digest","product_blueprint")}
    queued={kind:0 for kind in samples}
    recognized=0
    scanned=0
    for name in ("queue","processed"):
        folder=state/name
        if not safe_dir(folder):
            continue
        for p in folder.iterdir():
            scanned+=1
            if scanned>MAX_FILES:break
            if p.suffix!=".json" or p.is_symlink():continue
            request=read_record(p)
            if not request:continue
            kind=kind_of(request)
            if kind is None:continue
            if name=="queue":
                queued[kind]+=1
            else:
                # Only report a successfully completed draft if it can be
                # matched to its SHA256 input request; no fabricated counts.
                original_hash=hashlib.sha256(p.read_bytes()).hexdigest()[:24]
                result=read_record(state/"drafts"/(original_hash+".json"))
                if result and isinstance(result.get("draft"),dict):
                    row=result["draft"]
                    if (row.get("tenant")=="mojplaywin-main"
                        and row.get("review_required") is True
                        and row.get("published") is False):
                        recorded=date_of(result)
                        if recorded and recorded.isoformat() in period:
                            samples[kind][recorded.isoformat()]+=1
                        recognized+=1
        if scanned>MAX_FILES:break
    return days,samples,queued,recognized,scanned>MAX_FILES

def snapshot(now=None):
    if now is None:
        now=datetime.now(timezone.utc)
    today=now.date()
    empty_days=[(today-timedelta(days=n)).isoformat() for n in reversed(range(MAX_DAYS))]
    result={"source":"private_mojplaywin_cpanel_state","window_days":MAX_DAYS,
            "observed_at":now.isoformat(),
            "state":"unavailable","agents":[],"private_only":True,
            "auto_publish":False,"historical_failures_measured":False}
    if not safe_dir(PRIVATE_STATE):
        return result
    heartbeat=read_record(PRIVATE_STATE/"heartbeat.json") or {}
    stamp=heartbeat.get("last_master_callback_utc")
    fresh=False
    last=None
    if isinstance(stamp,str) and len(stamp)<40:
        try:
            last=datetime.fromisoformat(stamp.replace("Z","+00:00"))
            fresh=(last.tzinfo is not None and timedelta(0)<=now-last<=timedelta(hours=2))
        except (ValueError,TypeError):
            pass
    if (heartbeat.get("tenant")!="mojplaywin-main"
        or heartbeat.get("master_generation")!=64
        or heartbeat.get("auto_publish") is not False
        or heartbeat.get("factory_connected") is not False):
        return result
    days,samples,queued,recognized,truncated=count_private_runs(PRIVATE_STATE,today)
    master_status="active_private" if fresh else "stale_heartbeat"
    result.update({"state":master_status,
                   "last_master_callback_utc":stamp,
                   "truncated":truncated,
                   "agents":[
        {"id":"master_gen64","title":"مستر ایجنت نسل ۶۴",
         "setting":"کنترل اجرای خصوصی و هماهنگی","status":master_status,
         "schedule":"ساعتی؛ تنظیم‌شده در cPanel",
         "queue":None,"completed":None,"days":empty_days,
         "series":None,"history_available":False,
         "note":"فقط آخرین heartbeat ثبت می‌شود؛ سابقه روزانه مستر ایجنت هنوز ذخیره نمی‌شود."},
        {"id":"research_digest","title":"ایجنت مرور پژوهشی",
         "setting":"تهیه پیش‌نویس پژوهشی از متن منبع","status":master_status,
         "queue":queued["research_digest"],
         "completed":sum(samples["research_digest"].values()),
         "days":days,"series":list(samples["research_digest"].values()),
         "history_available":True,"note":"پیش‌نویس‌های تأییدشده در مخزن خصوصی، به تفکیک تاریخ تولید (UTC)."},
        {"id":"product_blueprint","title":"ایجنت طرح محصول",
         "setting":"تهیه طرح اولیه محصول، بدون فروش خودکار","status":master_status,
         "queue":queued["product_blueprint"],
         "completed":sum(samples["product_blueprint"].values()),
         "days":days,"series":list(samples["product_blueprint"].values()),
         "history_available":True,"note":"فقط فایل‌های خروجی دارای درخواست متناظر و هش منطبق شمارش می‌شوند."},
    ]})
    return result
