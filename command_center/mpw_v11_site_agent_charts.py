"""Real 14-day website monitoring charts, from isolated MojPlayWin V11 agent state.

Never connects to Zomorod, factory, databases or protected child sites.
Only confirmed completed private health checks are represented.
"""
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

HEALTH_STATE=Path("/home/zomorod2/.private_mojplaywin_main_agents/site_health_v11_port_20261018")
AUDIT_AGENTS=(
 ("master","ربات پایش اصلی سایت","بررسی پاسخ صفحه اصلی"),
 ("content","ربات پایش محتوا","بررسی صفحه دانش و محتوا"),
 ("seo","ربات پایش سئو","بررسی دسترسی صفحه جست‌وجو"),
 ("commerce","ربات پایش فروشگاه","بررسی پاسخ صفحه فروشگاه؛ بدون تراکنش"),
 ("agriculture","ربات پایش کشاورزی","بررسی بخش کشاورزی"),
 ("research","ربات پایش پژوهش","بررسی بخش پژوهش"),
 ("economic","ربات پایش اقتصاد","بررسی بخش اقتصاد"),
 ("weather","ربات پایش هواشناسی","بررسی در دسترس‌بودن صفحه هواشناسی"),
 ("quality","ربات کنترل کیفیت صفحات","بررسی صفحه معرفی شرکت"),
 ("media","ربات پایش رسانه","بررسی صفحه خبرنامه"),
 ("security","ربات پایش امنیت ورود","بررسی کد پاسخ ورود مدیریت، بدون ورود"),
)
N_DAYS=14
MAX_LINES=1600
MAX_BYTES=170000

def _is_private_dir(path):
    return path.is_dir() and not path.is_symlink() and (path.stat().st_mode & 0o077)==0

def _date(text):
    if not isinstance(text,str) or len(text)>40:
        return None
    try:
        value=datetime.fromisoformat(text.replace("Z","+00:00"))
        return value.astimezone(timezone.utc) if value.tzinfo else None
    except ValueError:
        return None

def site_agent_chart_rows(now=None,root=HEALTH_STATE):
    current=now or datetime.now(timezone.utc)
    days=[(current.date()-timedelta(days=i)).isoformat()
          for i in reversed(range(N_DAYS))]
    accepted_days=set(days)
    if not _is_private_dir(root):
        return []
    state={code:{"daily":defaultdict(lambda:{"ok":0,"warning":0,"error":0}),
                 "last":None,"last_status":None}
           for code,_,_ in AUDIT_AGENTS}
    last_seen=set()
    records=[]
    for file in (root/"history.previous.jsonl",root/"history.jsonl"):
        if file.is_symlink() or not file.is_file() or file.stat().st_size>MAX_BYTES:
            continue
        try:
            for line in file.read_text(encoding="utf-8").splitlines()[:MAX_LINES]:
                try:
                    obj=json.loads(line)
                except (ValueError,TypeError):
                    continue
                records.append(obj)
        except (OSError,UnicodeError):
            continue
    for row in records[:MAX_LINES]:
        if not isinstance(row,dict) or row.get("tenant")!="mojplaywin-main" or row.get("total_agents")!=11:
            continue
        stamp=_date(row.get("observed_utc"))
        if stamp is None or stamp>current+timedelta(minutes=5):
            continue
        day=stamp.date().isoformat()
        if day not in accepted_days:
            continue
        entries=row.get("runs")
        if not isinstance(entries,list) or len(entries)!=11:
            continue
        if set(e.get("code") for e in entries if isinstance(e,dict))!=set(state):
            continue
        for e in entries:
            code=e["code"]
            status=e.get("status")
            if status not in ("ok","warning","error"):
                continue
            key=(stamp.isoformat(),code)
            if key in last_seen:
                continue
            last_seen.add(key)
            agg=state[code]
            agg["daily"][day][status]+=1
            if agg["last"] is None or stamp>agg["last"]:
                agg["last"]=stamp
                agg["last_status"]=status
    rows=[]
    for code,title,mission in AUDIT_AGENTS:
        value=state[code]
        success=[value["daily"][day]["ok"] for day in days]
        warnings=sum(value["daily"][day]["warning"] for day in days)
        failures=sum(value["daily"][day]["error"] for day in days)
        last=value["last"]
        freshness=(last is not None and timedelta(0)<=current-last<=timedelta(hours=2))
        status=("unavailable" if last is None else
                "stale_heartbeat" if not freshness else
                "ok" if value["last_status"]=="ok" else value["last_status"])
        rows.append({
            "id":"site_v11_"+code,"title":title,"setting":mission,
            "status":status,
            "metric_kind":"site_health_checks",
            "queue":None,"completed":sum(success),
            "warning_count":warnings,"error_count":failures,
            "days":days,"series":success,
            "history_available":last is not None,
            "last_observed_utc":last.isoformat() if last else None,
            "note":"نمودار: تعداد پایش‌های موفق روزانه؛ هشدارها و خطاها جداگانه نمایش داده می‌شوند. فقط دامنه اصلی MojPlayWin."
        })
    return rows
