from django.conf import settings
from django.db import connection
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from rest_framework.response import Response
from rest_framework.status import HTTP_503_SERVICE_UNAVAILABLE
from rest_framework.views import APIView


@never_cache
def home(request):
    return render(
        request,
        "core/home.html",
        {
            "app_version": getattr(settings, "APP_VERSION", "0.1.0"),
        },
    )


class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception as exc:
            return Response(
                {
                    "status": "degraded",
                    "service": "saeit",
                    "database": "unavailable",
                    "error": exc.__class__.__name__,
                },
                status=HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "status": "ok",
                "service": "saeit",
                "version": getattr(settings, "APP_VERSION", "0.1.0"),
                "database": "ok",
            }
        )

def platform_page(request, section):
    pages = {
        "agriculture": {
            "kicker":"AGRICULTURE · VALUE CHAIN","title":"کشاورزی و زنجیره ارزش","lead":"از تحقیق و کشت تا فرآوری، بسته‌بندی، برند و بازار؛ هر زنجیره مستقل و قابل توسعه است.",
            "badge":"AGRICULTURE","heading":"زنجیره کشاورزی هوشمند","body":"ساختار این بخش برای اتصال دانش و عملیات واقعی کشاورزی طراحی شده است؛ بدون مخلوط‌کردن واحدها و با امکان توسعه هر زنجیره به‌صورت مستقل.",
            "items":[{"title":"پژوهش و کشت","text":"مطالعه، منابع، شواهد، برنامه‌ریزی و دانش فنی."},{"title":"فرآوری و بسته‌بندی","text":"تبدیل محصول خام به محصول استاندارد و قابل عرضه."},{"title":"برند و فروش","text":"اتصال محصول به بازار، سفارش و مسیر تجاری."}],
            "links":[{"title":"پژوهش","text":"منابع و گزارش‌ها","url":"/research/"},{"title":"محصولات","text":"کاتالوگ محصولات","url":"/market/"},{"title":"دانش","text":"دانش‌نامه تخصصی","url":"/knowledge/"}],
            "cta_title":"یک زنجیره کشاورزی را شروع کنیم","cta_text":"برای همکاری پژوهشی، تولیدی یا تجاری وارد مسیر شوید.","cta_label":"شروع همکاری","cta_url":"/contact/"
        },
        "industry": {
            "kicker":"INDUSTRY · PRODUCTION","title":"صنعت و تولید","lead":"زیرساختی برای توسعه محصول، فرآوری، بسته‌بندی و اتصال تولید به بازار.",
            "badge":"INDUSTRY","heading":"از طراحی تا تولید","body":"هر واحد صنعتی می‌تواند مستقل تعریف شود و از پژوهش و توسعه تا محصول نهایی، بازار و گزارش عملکرد مسیر مشخص داشته باشد.",
            "items":[{"title":"توسعه محصول","text":"تحقیق، نمونه‌سازی، استانداردسازی و مستندسازی."},{"title":"تولید و فرآوری","text":"مدیریت زنجیره تولید و تبدیل ارزش افزوده."},{"title":"بازار و برند","text":"بسته‌بندی، ارائه، سفارش و توسعه بازار."}],
            "links":[{"title":"بازار","text":"محصولات و خدمات","url":"/market/"},{"title":"پژوهش","text":"R&D","url":"/research/"},{"title":"همکاری","text":"فرصت‌های همکاری","url":"/contact/"}],
            "cta_title":"پروژه صنعتی خود را تعریف کنید","cta_text":"از مطالعه امکان‌سنجی تا تولید و بازار.","cta_label":"درخواست همکاری","cta_url":"/contact/"
        },
        "research": {
            "kicker":"RESEARCH · R&D","title":"پژوهش و توسعه","lead":"پژوهش، منبع، شواهد، یافته و گزارش در یک مسیر قابل ردیابی.",
            "badge":"RESEARCH","heading":"Research → Knowledge","body":"هسته پژوهشی، منشأ اطلاعات را حفظ می‌کند و خروجی پژوهش را به پیش‌نویس دانش تبدیل می‌کند؛ انتشار دانش یک مرحله مستقل و نیازمند تأیید مالک است.",
            "items":[{"title":"Project","text":"تعریف هدف و مرز مالکیت پروژه."},{"title":"Evidence","text":"ثبت منبع و شواهد با کنترل تعلق پروژه."},{"title":"Report","text":"ساخت گزارش نسخه‌بندی‌شده و قابل تبدیل به دانش."}],
            "links":[{"title":"دانش","text":"پیش‌نویس‌ها و مقالات","url":"/knowledge/"},{"title":"عامل‌ها","text":"اجرای وظایف پژوهشی","url":"/agents/"},{"title":"API","text":"دسترسی برنامه‌نویسی","url":"/api/"}],
            "cta_title":"پژوهش را به ارزش تبدیل کنید","cta_text":"پروژه، گزارش و دانش را در یک زنجیره نگه دارید.","cta_label":"مشاهده API","cta_url":"/api/"
        },
        "knowledge": {
            "kicker":"KNOWLEDGE · ENCYCLOPEDIA","title":"دانش‌نامه Zomorodmelal","lead":"دانش قابل استفاده، با منشأ روشن و اتصال مستقیم به پژوهش.",
            "badge":"KNOWLEDGE","heading":"پایگاه دانش","body":"مقالات دانش از گزارش‌های پژوهشی ایجاد می‌شوند و قبل از انتشار عمومی، مسیر تأیید مالک را طی می‌کنند. این معماری امکان ساخت Topic Cluster و Pillar Page را فراهم می‌کند.",
            "items":[{"title":"Pillar Pages","text":"صفحات مرجع برای موضوعات اصلی."},{"title":"Topic Clusters","text":"خوشه‌بندی دانش پیرامون موضوعات تخصصی."},{"title":"Provenance","text":"ردپای گزارش پژوهشی منبع هر مقاله."},{"title":"Glossary","text":"واژه‌نامه استاندارد برای مفاهیم و اصطلاحات کلیدی."},{"title":"Research Notes","text":"یادداشت‌های پژوهشی برای اتصال شواهد به دانش."},{"title":"Knowledge Graph","text":"رابطه‌دادن موضوعات، منابع، محصولات و یافته‌ها."}],
            "links":[{"title":"گزارش‌ها","text":"منبع دانش","url":"/api/reports/"},{"title":"محصولات","text":"اتصال دانش به محصول","url":"/market/"},{"title":"پژوهش","text":"هسته پژوهشی","url":"/research/"}],
            "cta_title":"دانش را به محصول متصل کنید","cta_text":"مقاله، محصول و بازار را در یک معماری منسجم قرار دهید.","cta_label":"مشاهده محصولات","cta_url":"/market/"
        },
        "market": {
            "kicker":"MARKET · PRODUCTS","title":"بازار و محصولات","lead":"محصول و خدمت، سفارش و پرداخت کنترل‌شده؛ آماده برای توسعه به یک Super Platform تجاری.",
            "badge":"MARKET","heading":"مسیر تجاری کنترل‌شده","body":"محصول فقط پس از اتصال به دانش منتشرشده و تأیید مالک فعال می‌شود. سفارش، Payment Intent، Webhook امضاشده، Ledger و Audit در هسته عملیاتی قرار گرفته‌اند.",
            "items":[{"title":"Product","text":"محصول یا خدمت با منشأ دانش."},{"title":"Order","text":"سفارش با قیمت و ارز Snapshot شده."},{"title":"Payment","text":"پرداخت idempotent با تأیید مالک و ثبت Ledger."}],
            "links":[{"title":"محصولات API","text":"کاتالوگ عملیاتی","url":"/api/products/"},{"title":"سفارش‌ها","text":"چرخه سفارش","url":"/api/orders/"},{"title":"دانش","text":"منشأ محصولات","url":"/knowledge/"}],
            "cta_title":"بازار را گسترش دهید","cta_text":"درگاه واقعی، Refund و Reconciliation در گام‌های بعدی به همین هسته متصل می‌شوند.","cta_label":"تماس تجاری","cta_url":"/contact/"
        },
        "agents": {
            "kicker":"AI · MASTER AGENT","title":"عامل‌های هوشمند","lead":"هوش مصنوعی برای پژوهش و عملیات، با توقف اجباری در عملیات حساس.",
            "badge":"AGENTS","heading":"Master Agent و Workerها","body":"عامل‌ها می‌توانند برنامه‌ریزی، وظیفه، قابلیت و اجرای قابل حسابرسی داشته باشند. عملیات حساس مانند انتشار، پرداخت، استقرار و تغییرات تولیدی بدون تأیید مالک اجرا نمی‌شوند.",
            "items":[{"title":"Master Agent","text":"مدیریت و برنامه‌ریزی مرکزی."},{"title":"Worker Agents","text":"اجرای وظایف تخصصی با Capability مشخص."},{"title":"Governance","text":"Approval Grant یک‌بارمصرف، کوتاه‌مدت و محدود به Scope."}],
            "links":[{"title":"وضعیت","text":"Health و Production Gate","url":"/api/health/"},{"title":"مدیریت","text":"کنترل و Audit","url":"/admin/"},{"title":"پژوهش","text":"محیط اجرای پژوهش","url":"/research/"}],
            "cta_title":"یک عامل را وارد زنجیره کنید","cta_text":"عامل‌ها باید در کنار انسان کار کنند، نه بدون کنترل انسانی.","cta_label":"شروع همکاری","cta_url":"/contact/"
        },
        "about": {
            "kicker":"ZOMORODMELAL · ABOUT","title":"درباره Zomorodmelal","lead":"یک بستر برای پیوند پژوهش، دانش، تولید، فناوری و بازار.",
            "badge":"COMPANY PORTAL","heading":"پورتال شرکت و اکوسیستم","body":"این صفحه درگاه معرفی ساختار، حوزه‌های فعالیت، فرصت‌های همکاری و مسیرهای توسعه پلتفرم است. ظاهر و معماری بخش‌ها مستقل است اما همه به هسته مرکزی متصل می‌شوند.",
            "items":[{"title":"پژوهش و فناوری","text":"توسعه دانش و فناوری برای زنجیره‌های تخصصی."},{"title":"کشاورزی و صنعت","text":"توسعه زنجیره‌های ارزش مستقل."},{"title":"همکاری و درآمد","text":"پروژه، محصول، خدمت و همکاری تجاری."}],
            "links":[{"title":"حوزه‌ها","text":"کشاورزی و صنعت","url":"/agriculture/"},{"title":"پلتفرم","text":"ساختار فنی و AI","url":"/agents/"},{"title":"تماس","text":"فرصت‌های همکاری","url":"/contact/"}],
            "cta_title":"برای همکاری با ما ارتباط بگیرید","cta_text":"مسیر همکاری را بر اساس حوزه و ظرفیت شما تعریف می‌کنیم.","cta_label":"تماس با ما","cta_url":"/contact/"
        },
        "contact": {
            "kicker":"CONTACT · COLLABORATION","title":"تماس و همکاری","lead":"برای پژوهش، تولید، صنعت، فناوری، محصول و بازار با ما در ارتباط باشید.",
            "badge":"COLLABORATION","heading":"درخواست همکاری","body":"نوع همکاری، حوزه فعالیت و هدف خود را مشخص کنید. این صفحه در گام بعدی می‌تواند به فرم واقعی، CRM و عامل پیگیری درخواست متصل شود.",
            "items":[{"title":"پژوهشی","text":"پروژه تحقیقاتی، مطالعه بازار و R&D."},{"title":"تولیدی و صنعتی","text":"تولید، فرآوری، بسته‌بندی و توسعه محصول."},{"title":"فناوری و AI","text":"عامل‌ها، API، اتوماسیون و توسعه پلتفرم."}],
            "links":[{"title":"پژوهش","text":"مشاهده ساختار پژوهش","url":"/research/"},{"title":"بازار","text":"محصولات و خدمات","url":"/market/"},{"title":"وضعیت سامانه","text":"Health","url":"/api/health/"}],
            "cta_title":"قدم بعدی را شروع کنیم","cta_text":"این بخش آماده است تا در مرحله بعد به فرم و گردش‌کار واقعی متصل شود.","cta_label":"مشاهده API","cta_url":"/api/"
        }
    }
    page = pages.get(section)
    if page is None:
        from django.http import Http404
        raise Http404
    return render(request, "core/platform_page.html", {"page": page})
