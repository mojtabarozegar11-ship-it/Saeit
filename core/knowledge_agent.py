from django.utils import timezone
from .models import Agent, AgentTask
from .knowledge_agent_models import KnowledgeAgentPlan, KnowledgeDomain, KnowledgeBook, KnowledgeAgentRun
from .knowledge_quality import quality_contract

DEFAULT_OUTLINE = [
    "تعریف مسئله و دامنه",
    "مفاهیم و واژگان کلیدی",
    "شواهد و منابع قابل ردیابی",
    "روش و چارچوب تحلیل",
    "یافته‌ها و نکات کاربردی",
    "محدودیت‌ها و عدم‌قطعیت",
    "موضوعات مرتبط و مسیر مطالعه بعدی",
]

START = timezone.datetime(2019, 11, 16).date()
BOOKS = [
("food-agriculture", "صنایع غذایی و کشاورزی", "صنایع غذایی و کشاورزی", "تولید، فرآوری، ایمنی غذا، کیفیت و کشاورزی نوین"),
("culinary-cafe-restaurant", "آشپزی، کافه و رستوران‌داری", "آشپزی و مهمان‌داری", "آشپزی حرفه‌ای، قهوه، منو، عملیات و مدیریت"),
("gem-gold-jewelry", "گوهرسنگ، طلا و جواهرات", "گوهرشناسی و جواهرات", "شناخت، ارزیابی، طراحی، ساخت، عیار و اصالت"),
("iranian-coins", "سکه‌های ایران در طول تاریخ", "سکه‌شناسی ایران", "دوره‌های تاریخی، ضرابخانه، گونه‌ها و منابع مستند"),
("carpet-handicrafts", "فرش و صنایع دستی", "میراث و هنرهای سنتی", "فرش، نقوش، مواد، بافت، اصالت و حفاظت"),
("agri-economics-farm-management", "اقتصاد کشاورزی، اقتصاد تولید و مدیریت مزارع", "اقتصاد و مدیریت کشاورزی", "هزینه، درآمد، بهره‌وری، برنامه‌ریزی و مدیریت مزرعه"),
("company-specialized-library", "کتاب‌های تخصصی حوزه‌های فعالیت شرکت", "حوزه‌های فعالیت شرکت", "کشاورزی، صنعت، فناوری، ژنتیک، بازار و زنجیره‌های تخصصی"),
("reference-encyclopedias", "کتاب‌های مرجع و دانشنامه‌های تخصصی", "مرجع و دانشنامه", "تعاریف، روش‌ها، منابع و مفاهیم تخصصی"),
("shia-islamic-studies", "دانشنامه معارف و منابع اسلامی شیعه", "مطالعات اسلامی شیعه", "قرآن، حدیث، سیره، کلام، فقه، اخلاق و تاریخ با استناد دقیق"),
("quran-encyclopedia", "دانشنامه جامع قرآن کریم", "قرآن‌پژوهی", "سوره، آیه، واژه، مفهوم، موضوع، تفسیر و منابع معتبر"),
("occult-history-27-volumes", "مجموعه ۲۷ جلدی علوم غریبه", "مطالعات تاریخی و متنی", "فهرست‌سازی تاریخی و متنی آثار با تفکیک منبع و اعتبارسنجی"),
]

def ensure_plan():
    plan, _ = KnowledgeAgentPlan.objects.get_or_create(code="knowledge-content-director", defaults={
        "title":"Knowledge Content Director", "mission":"تحقیق، طراحی، تولید، بازبینی و توسعه مستمر کتابخانه دانشنامه‌ای شرکت.",
        "goal":"ساخت کتابخانه‌ای زنده، قابل استناد و قابل گسترش از تاریخ ۲۵ آبان ۱۳۹۸ به بعد با هدف سئو، جذب مخاطب و ارائه دانش رایگان.", "public_free":True, "seo_first":True, "audience_goal":"ساخت محتوای ارزشمند و مرجع برای جذب مخاطب از جست‌وجو؛ دسترسی عمومی و رایگان.", "start_date":START,
        "cadence_hours":24, "require_owner_approval":True,
    })
    return plan

def seed_library():
    plan = ensure_plan()
    for index, (code, title, domain, objective) in enumerate(BOOKS, 1):
        d, _ = KnowledgeDomain.objects.get_or_create(code=code, defaults={"title":domain,"scientific_scope":objective,"priority":index})
        book, _ = KnowledgeBook.objects.get_or_create(code=code, defaults={"plan":plan,"domain_ref":d,"title":title,"domain":domain,"objective":objective,"status":"planned"})
        if not book.outline:
            book.outline = DEFAULT_OUTLINE
            book.save(update_fields=["outline", "updated_at"])
    return plan

def queue_cycle():
    plan = seed_library()
    now = timezone.now()
    if not plan.active:
        return None
    active_run = plan.runs.filter(status__in=("queued", "running")).exists()
    if active_run:
        return None
    if plan.next_run_at and plan.next_run_at > now:
        return None
    book = plan.books.exclude(status="published").order_by("generated_sections", "id").first()
    if not book:
        plan.last_run_at = now
        plan.next_run_at = None
        plan.save(update_fields=["last_run_at", "next_run_at", "updated_at"])
        return None
    run = KnowledgeAgentRun.objects.create(plan=plan, book=book, objective=f"تولید بخش بعدی برای {book.title}؛ مبنا از {START.isoformat()}؛ با منابع قابل ردیابی.", approval_required=plan.require_owner_approval)
    agent, _ = Agent.objects.get_or_create(code="knowledge-content-director", defaults={"name":"Knowledge Content Director","mission":plan.mission,"risk_level":"low","active":True})
    AgentTask.objects.create(agent=agent, action_type="knowledge_content_generation", capability_code="research-write-review", risk_snapshot="low", input_data={"run_id":run.id,"book_id":book.id,"start_date":START.isoformat()}, status="queued")
    plan.last_run_at = now
    plan.next_run_at = now + timezone.timedelta(hours=plan.cadence_hours)
    plan.save(update_fields=["last_run_at", "next_run_at", "updated_at"])
    return run
