from django.core.management.base import BaseCommand
from django.utils.text import slugify

from core.models import EducationCourse, EducationTrack, Product


CATALOG = [
    ("school", "ریاضی پایه؛ از مفهوم تا حل مسئله", "مسیر مفهومی ریاضی برای ساخت پایه محکم از ابتدایی تا متوسطه.", ["عدد و محاسبات", "جبر و الگو", "هندسه", "آمار و احتمال", "حل مسئله", "تمرین و جمع‌بندی"]),
    ("konkur", "آمادگی کنکور؛ درس، تست و جمع‌بندی", "چارچوب مرحله‌ای برای مطالعه، تست‌زنی، تحلیل آزمون و جمع‌بندی.", ["شناخت آزمون", "مطالعه مفهومی", "تست آموزشی", "تست زمان‌دار", "تحلیل آزمون", "جمع‌بندی و مرور"]),
    ("university", "مهارت پژوهش دانشگاهی و مقاله", "از پرسش پژوهش تا جست‌وجوی منبع، تحلیل، نگارش و ارائه.", ["پرسش پژوهش", "جست‌وجوی منابع", "روش تحقیق", "تحلیل داده", "نگارش علمی", "ارائه و بازبینی"]),
    ("technical", "برنامه‌نویسی کاربردی؛ از منطق تا پروژه", "مسیر مهارتی برای ساخت پایه برنامه‌نویسی و تبدیل آن به پروژه واقعی.", ["منطق و الگوریتم", "ساختار داده مقدماتی", "Python", "کار با API", "تست و دیباگ", "پروژه نهایی"]),
    ("agri", "اصول تولید کشاورزی و زنجیره ارزش", "آموزش عملی از شناخت تولید تا کیفیت، فرآوری، بسته‌بندی و بازار.", ["شناخت زنجیره", "تولید و عملیات", "کنترل کیفیت", "فرآوری", "بسته‌بندی", "بازار و فروش"]),
    ("industry", "مدیریت تولید و زنجیره ارزش", "مبانی طراحی، کنترل و بهبود مسیر تولید تا عرضه محصول.", ["طراحی فرآیند", "برنامه‌ریزی تولید", "کیفیت", "هزینه و بهره‌وری", "بسته‌بندی و لجستیک", "بازار و بهبود مستمر"]),
    ("ai", "هوش مصنوعی و عامل‌های هوشمند", "از مبانی AI تا طراحی عامل، اتوماسیون و استفاده مسئولانه.", ["مبانی AI", "مدل‌ها و داده", "Prompt Engineering", "Agent Architecture", "Automation", "ارزیابی و حاکمیت"]),
    ("business", "مدل کسب‌وکار، بازاریابی و فروش", "مسیر عملی برای طراحی ارزش پیشنهادی، بازار، فروش و درآمد پایدار.", ["مسئله و مشتری", "ارزش پیشنهادی", "مدل درآمد", "بازاریابی", "فروش", "تحلیل و رشد"]),
]


class Command(BaseCommand):
    help = "Seed the education catalog as inactive draft courses; never publishes content."

    def handle(self, *args, **options):
        created = 0
        for key, title, summary, syllabus in CATALOG:
            track = EducationTrack.objects.filter(key=key).first()
            if not track:
                self.stdout.write(self.style.WARNING(f"SKIP {key}: track not found"))
                continue
            slug = slugify(title, allow_unicode=True)
            course, was_created = EducationCourse.objects.get_or_create(
                slug=slug,
                defaults={
                    "track": track,
                    "title": title,
                    "summary": summary,
                    "syllabus": syllabus,
                    "prerequisites": "پیش‌نیازها پس از طراحی سطح‌بندی نهایی می‌شوند.",
                    "outcome": "خروجی‌های قابل سنجش پس از تکمیل محتوای دوره نهایی می‌شوند.",
                    "is_free": key == "school",
                    "active": False,
                    "approved": False,
                    "quality_status": "draft",
                },
            )
            if was_created:
                created += 1
            self.stdout.write(f"DRAFT | {course.slug} | created={was_created}")
        self.stdout.write(f"Seeded {created} new draft course(s); nothing was published.")
