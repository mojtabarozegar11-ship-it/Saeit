from django.db import migrations


def seed_newsletter(apps, schema_editor):
    Agent = apps.get_model("core", "Agent")
    NewsletterAgentLink = apps.get_model("core", "NewsletterAgentLink")
    NewsletterSchedule = apps.get_model("core", "NewsletterSchedule")
    NewsletterSource = apps.get_model("core", "NewsletterSource")

    parent, _ = Agent.objects.get_or_create(
        code="newsletter-specialist",
        defaults={"name": "ایجنت تخصصی خبرنامه", "mission": "مدیریت تولید، کنترل کیفیت، عدم تکرار، سئو و توزیع خبرنامه علمی و مستند.", "risk_level": "medium", "active": False},
    )
    children = [
        ("newsletter-company-news", "ایجنت اخبار فعالیت شرکت", "روزانه ۴ خبر فقط بر پایه فعالیت‌ها و داده‌های واقعی ثبت‌شده شرکت."),
        ("newsletter-world-watch", "ایجنت رصد اخبار جهان", "گردآوری اخبار معتبر جهانی مرتبط با حوزه‌های شرکت، با ذکر منبع اصلی."),
        ("newsletter-unit-reports", "ایجنت گزارش فعالیت واحدها", "روزانه ۴ گزارش مستقل از داده‌های واقعی واحدها، پروژه‌ها و پژوهش‌ها."),
    ]
    for sequence, (code, name, mission) in enumerate(children, 1):
        child, _ = Agent.objects.get_or_create(
            code=code,
            defaults={"name": name, "mission": mission, "risk_level": "medium", "active": False},
        )
        NewsletterAgentLink.objects.update_or_create(
            child=child,
            defaults={"parent": parent, "sequence": sequence, "responsibility": mission},
        )

    NewsletterSchedule.objects.get_or_create(
        pk=1,
        defaults={
            "company_news_daily": 4,
            "world_news_daily": 4,
            "reports_daily": 4,
            "publication_requires_approval": True,
            "active": True,
        },
    )

    sources = [
        ("FAO", "FAO Newsroom", "https://www.fao.org/newsroom/en", "world"),
        ("Nature Biotechnology", "News & Comment", "https://www.nature.com/nbt/news-and-comment", "research"),
    ]
    for publisher, title, url, kind in sources:
        NewsletterSource.objects.get_or_create(url=url, defaults={"publisher": publisher, "title": title, "kind": kind})


def unseed_newsletter(apps, schema_editor):
    Agent = apps.get_model("core", "Agent")
    NewsletterAgentLink = apps.get_model("core", "NewsletterAgentLink")
    NewsletterSchedule = apps.get_model("core", "NewsletterSchedule")
    NewsletterSource = apps.get_model("core", "NewsletterSource")
    NewsletterAgentLink.objects.all().delete()
    Agent.objects.filter(code__in=["newsletter-specialist", "newsletter-company-news", "newsletter-world-watch", "newsletter-unit-reports"]).delete()
    NewsletterSchedule.objects.filter(pk=1).delete()
    NewsletterSource.objects.filter(url__in=["https://www.fao.org/newsroom/en", "https://www.nature.com/nbt/news-and-comment"]).delete()


class Migration(migrations.Migration):
    dependencies = [("core", "0016_newsletterschedule_newslettersource_newsletterstory_and_more")]
    operations = [migrations.RunPython(seed_newsletter, unseed_newsletter)]
