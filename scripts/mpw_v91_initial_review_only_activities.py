"""Seed two genuine *review-only* MojPlayWin content jobs and run one bounded cycle.

This writes solely to the verified *private* V91 operator_state queue on cPanel.
No webroot, Django, Passenger, shared DB, factory, subsites or public publication.
"""
import hashlib,json,os,sys
from pathlib import Path

STAGE=Path("/home/zomorod2/.private_mojplaywin_main_agents/v91_verified_main_port_20261018")
STATE=STAGE/"operator_state"
QUEUE=STATE/"queue"
DONE=STATE/"processed"
DRAFTS=STATE/"drafts"
ROOT=Path("/home/zomorod2/.private_mojplaywin_main_agents")
ARTICLES=(
{
 "tenant":"mojplaywin-main","review_only":True,"kind":"research_digest",
 "title":"چارچوب پژوهشی ارزیابی کیفیت بازی‌های آموزشی مرورگر",
 "summary":"پیش‌نویس پژوهشی اختصاصی برای مج پلی وین درباره سنجش یادگیری، دسترس‌پذیری و تجربه کاربر در بازی‌های آموزشی تحت وب است. تمام منابع باید پیش از انتشار توسط مسئول محتوا بازبینی شوند.",
 "body":(
  "هدف این طرح تدوین چارچوب ارزیابی بازی آموزشی برای مخاطبان جهانی مج پلی وین است. "
  "پیش از طراحی، اهداف قابل‌اندازه‌گیری یادگیری و گروه سنی مخاطب ثبت شوند. "
  "نسخه آزمایشی باید با مشارکت کاربران واقعی از نظر فهم مأموریت، وضوح راهنماها و امکان بازی با صفحه‌کلید بررسی شود. "
  "داده‌های آزمون با رضایت آگاهانه و حداقل اطلاعات شخصی جمع‌آوری شوند. "
  "برای هر معیار یک روش سنجش روشن و امکان تکرار آزمون تعریف شود. "
  "پیشنهاد پژوهشی شامل مقایسه دو سناریوی طراحی و تحلیل خطاهای رایج است. "
  "این متن پیش‌نویس داخلی محسوب می‌شود و ارزیابی علمی، راستی‌آزمایی منابع، و تأیید حقوقی پیش از انتشار لازم است. "
 )*2,
 "sources":["https://www.w3.org/TR/WCAG22/"],
},
{
 "tenant":"mojplaywin-main","review_only":True,"kind":"product_blueprint",
 "title":"طرح محصول دیجیتال بسته طراحی بازی آموزشی تحت وب",
 "summary":"طرح اولیه یک محصول دیجیتال آموزشی قابل توسعه برای مج پلی وین، شامل نقشه یادگیری، تمرین‌های عملی، نمونه پروژه و معیارهای کیفیت است. این سند پیشنهاد داخلی است و هنوز برای فروش یا انتشار تأیید نشده است.",
 "body":(
  "این محصول پیشنهادی از بخش‌های مبانی طراحی بازی، تعریف هدف یادگیری، طراحی مرحله، رابط کاربری دسترس‌پذیر، "
  "آزمون کیفیت، مستندسازی انتشار و ارزیابی بازخورد کاربران تشکیل می‌شود. "
  "خروجی هر بخش باید یک تمرین مستقل و یک فایل نمونه با مجوز روشن باشد. "
  "برای محصول نهایی لازم است سطح مقدماتی و پیشرفته، زمان تقریبی مطالعه، دسترسی برای موبایل، "
  "الزامات حریم خصوصی، روش پشتیبانی پس از خرید و سیاست بازپرداخت مشخص شوند. "
  "بازبینی محتوایی و کنترل اصالت تصویر و متن الزامی است. "
  "این صرفاً طرح داخلی است؛ نه محصول ساخته و منتشر شده و نه کالای آماده فروش. "
 )*2,
 "sources":["https://www.w3.org/TR/WCAG22/"],
},
)
def private(p):
    return p.is_dir() and not p.is_symlink() and p.stat().st_mode & 0o077 == 0

def main():
    os.umask(0o077)
    if not private(ROOT) or not private(STAGE) or not private(STATE):
        raise SystemExit("PRIVATE_SOURCE_OR_STATE_INVALID")
    for name in ("queue","processed","drafts"):
        p=STATE/name
        if p.is_symlink():
            raise SystemExit("INVALID_STATE_SYMLINK")
        p.mkdir(mode=0o700,exist_ok=True)
        if not private(p):
            raise SystemExit("INVALID_PRIVATE_QUEUE_PERMISSIONS")
    enabled=STATE/"enabled"
    if enabled.is_symlink() or not enabled.is_file() or enabled.read_text().strip()!="MPW_V91_MAIN_ONLY_PRIVATE_20261018":
        raise SystemExit("OWNER_PRIVATE_WORKER_NOT_ENABLED")
    sys.path.insert(0,str(STAGE))
    from mpw_v91_port.worker import origin_ok,tick
    from mpw_v91_port.runtime import _validate
    if not origin_ok():
        raise SystemExit("UNVERIFIED_V91_MASTER_SOURCE")
    created=0
    for payload in ARTICLES:
        kind=payload["kind"]
        _validate(payload)
        raw=json.dumps(payload,sort_keys=True,ensure_ascii=False).encode("utf8")
        if len(raw)>12000:
            raise SystemExit("TASK_OUTSIDE_WORKER_BUDGET")
        digest=hashlib.sha256(raw).hexdigest()[:24]
        name="mpw-main-initial-"+digest+".json"
        if (QUEUE/name).is_symlink() or (DONE/name).is_symlink():
            raise SystemExit("UNSAFE_TASK_RECORD")
        if (QUEUE/name).is_file() or (DONE/name).is_file():
            continue
        fd=os.open(str(QUEUE/name),os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o600)
        with os.fdopen(fd,"wb") as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        created+=1
    os.environ["PYTHONDONTWRITEBYTECODE"]="1"
    status=tick()
    draft_count=0
    for payload in ARTICLES:
        raw=json.dumps(payload,sort_keys=True,ensure_ascii=False).encode("utf8")
        digest=hashlib.sha256(raw).hexdigest()[:24]
        if not (DONE/("mpw-main-initial-"+digest+".json")).is_file():
            continue
        result=DRAFTS/(digest+".json")
        if result.is_symlink() or not result.is_file() or result.stat().st_size>24000:
            continue
        try:
            meta=json.loads(result.read_text(encoding="utf8"))
            draft=meta.get("draft",{})
            if (draft.get("tenant")=="mojplaywin-main"
                and draft.get("review_required") is True
                and draft.get("published") is False
                and draft.get("sale_ready") is False):
                draft_count+=1
        except (OSError,UnicodeError,ValueError,TypeError):
            continue
    result={"classification":"MPW_V91_EDITORIAL_AGENT_INITIAL_PRIVATE_PRODUCTION",
            "worker_result":status.get("status"),
            "queued_initial_tasks_created":created,
            "review_drafts_verified":draft_count,
            "expected_review_drafts":len(ARTICLES),
            "auto_published":False,
            "website_modified":False,"other_subsites_modified":False,
            "factory_modified":False}
    print(json.dumps(result,sort_keys=True))
    if status.get("status")!="active_private" or draft_count!=len(ARTICLES):
        raise SystemExit(2)
if __name__=="__main__":
    main()
