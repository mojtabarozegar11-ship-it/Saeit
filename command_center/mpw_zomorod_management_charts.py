"""Real private-state dashboard entries for Zomorod-derived MPW policy agents.

Each has only one recent proof snapshot, NOT full daily history. All unobserved
days are null; never infer zero attempts or failures from missing records.
"""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json

ROOT=Path("/home/zomorod2/.private_mojplaywin_main_agents/management_intelligence_20261018")
ROLES=(
 ("company_activity_intelligence","ایجنت گزارش مدیریتی","آخرین خلاصه عملیاتی بر پایه داده واقعی ایجنت‌های MojPlayWin","latest_company_operations.json","operational_brief"),
 ("economic_master_policy","ایجنت سیاست اقتصادی","بررسی پیشنهادهای اقتصادی، بدون اجرای مالی","latest_economic_policy.json","economic_policy"),
)
def read_report(file):
    if not file.is_file() or file.is_symlink() or file.stat().st_size>35000:
        return None
    try:
        data=json.loads(file.read_text(encoding="utf8"))
        return data if isinstance(data,dict) and data.get("tenant")=="mojplaywin-main" else None
    except (OSError,ValueError,UnicodeError):
        return None

def rows(now=None,root=ROOT):
    now=now or datetime.now(timezone.utc)
    days=[(now.date()-timedelta(days=n)).isoformat() for n in reversed(range(14))]
    results=[]
    private=root.is_dir() and not root.is_symlink() and root.stat().st_mode&0o077==0
    for code,title,mission,filename,kind in ROLES:
        payload=read_report(root/filename) if private else None
        time=None
        role=payload.get("report",{}) if payload else {}
        if not isinstance(role,dict) or role.get("id")!=code or role.get("published") is not False:
            payload=None
        if payload:
            try:
                time=datetime.fromisoformat(str(payload["observed_utc"]).replace("Z","+00:00"))
                if time.tzinfo is None or time>now+timedelta(minutes=5):time=None
            except (KeyError,ValueError,TypeError):time=None
        fresh=time is not None and timedelta(0)<=now-time<=timedelta(hours=2)
        day=time.date().isoformat() if time is not None else None
        measured=day in days
        results.append({
            "id":code,"title":title,"setting":mission,"metric_kind":kind,
            "status":"active_private" if fresh else "stale_heartbeat" if time else "unavailable",
            "days":days,"series":[1 if d==day else None for d in days] if measured else None,
            "history_available":measured,"chart_type":"last_observation",
            "queue":None,"completed":1 if measured else None,
            "last_observed_utc":time.isoformat() if time else None,
            "note":"فقط آخرین اجرای واقعی ثبت شده است. روزهای بدون سابقه، نامشخص هستند؛ انتشار و عملیات مالی مجاز نیست.",
        })
    return results
