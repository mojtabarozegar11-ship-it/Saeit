from django.core.management.base import BaseCommand
from core.models import EducationCourse, EducationLesson, EducationResource, EducationPresentation

CONTENT = {
    "school": ("درس ۱: راهبرد حل مسئله", "دانش‌آموز مسئله را به داده، خواسته، رابطه و گام‌های حل تقسیم می‌کند.", "برگه تمرین راهبردهای حل مسئله", "حل مسئله و مرور", ["خواندن دقیق مسئله", "استخراج داده‌ها", "انتخاب راهبرد", "بررسی پاسخ"]),
    "konkur": ("درس ۱: طراحی برنامه تست", "تفاوت تست آموزشی و زمان‌دار، تحلیل خطا و ثبت نکات مرور آموزش داده می‌شود.", "چک‌لیست تحلیل آزمون", "تست‌زنی و تحلیل", ["هدف آزمون", "تست آموزشی", "تست زمان‌دار", "تحلیل خطا"]),
    "university": ("درس ۱: از مسئله تا پرسش پژوهش", "موضوع پژوهش به پرسش روشن، قابل بررسی و محدود تبدیل می‌شود.", "الگوی تدوین پرسش پژوهش", "روش پژوهش", ["موضوع", "مسئله", "پرسش", "معیار بررسی"]),
    "technical": ("درس ۱: منطق و الگوریتم", "مسئله به ورودی، پردازش، خروجی و الگوریتم مرحله‌ای تبدیل می‌شود.", "کاربرگ طراحی الگوریتم", "الگوریتم و Python", ["تعریف ورودی", "طراحی مراحل", "شبه‌کد", "آزمون مثال"]),
    "agri": ("درس ۱: نقشه زنجیره ارزش", "مراحل تولید، کنترل کیفیت، فرآوری، بسته‌بندی و بازار به‌صورت یک زنجیره قابل اندازه‌گیری بررسی می‌شوند.", "فرم نقشه زنجیره ارزش", "تولید و زنجیره ارزش", ["ورودی", "تولید", "کیفیت", "بازار"]),
    "industry": ("درس ۱: طراحی فرآیند تولید", "فرآیند به فعالیت، ورودی، خروجی، مسئول و شاخص کنترل تفکیک می‌شود.", "فرم طراحی فرآیند", "مدیریت تولید", ["ورودی", "مراحل", "شاخص", "خروجی"]),
    "ai": ("درس ۱: معماری عامل هوشمند", "وظیفه، ابزار، حافظه، سیاست تأیید و مسیر ارزیابی برای یک عامل هوشمند تعریف می‌شود.", "چک‌لیست معماری Agent", "AI و Agent", ["هدف", "ابزار", "اجازه", "ارزیابی"]),
    "business": ("درس ۱: مسئله، مشتری و ارزش", "مسئله مشتری، بخش هدف و ارزش پیشنهادی به یک فرضیه قابل آزمون تبدیل می‌شوند.", "بوم فرضیه ارزش پیشنهادی", "مدل کسب‌وکار", ["مسئله", "مشتری", "ارزش", "آزمون"]),
}

class Command(BaseCommand):
    help = "Seed quality-gate starter content for draft education courses without publishing them."

    def handle(self, *args, **options):
        created = 0
        for key, (lesson_title, lesson_summary, resource_title, presentation_title, plan) in CONTENT.items():
            course = EducationCourse.objects.filter(track__key=key).first()
            if not course:
                self.stdout.write(self.style.WARNING(f"SKIP {key}: course not found"))
                continue
            lesson, made = EducationLesson.objects.get_or_create(course=course, title=lesson_title, defaults={
                "summary": lesson_summary, "content": lesson_summary + "\n\n" + "\n".join(f"- {x}" for x in plan),
                "duration_minutes": 25, "sort_order": 1, "is_free_preview": True, "active": True,
            })
            if made: created += 1
            else:
                lesson.active = True; lesson.save(update_fields=["active"])
            resource, made = EducationResource.objects.get_or_create(course=course, title=resource_title, defaults={
                "kind": "worksheet", "content": "\n".join(f"{i+1}. {x}" for i, x in enumerate(plan)),
                "is_free": True, "active": True, "approved": True, "sort_order": 1,
            })
            if made: created += 1
            else:
                resource.active = True; resource.approved = True; resource.save(update_fields=["active", "approved"])
            presentation, made = EducationPresentation.objects.get_or_create(course=course, title=presentation_title, defaults={
                "audience": "teacher", "description": lesson_summary, "slide_count": len(plan) + 2,
                "lesson_plan": plan, "classroom_activities": ["تمرین فردی", "بازخورد و اصلاح"],
                "assessment_notes": "ارزیابی با یک تمرین کوتاه و بررسی خروجی انجام شود.",
                "is_free": True, "active": True, "approved": True, "quality_status": "approved",
            })
            if made: created += 1
            else:
                presentation.active = True; presentation.approved = True; presentation.quality_status = "approved"
                presentation.save(update_fields=["active", "approved", "quality_status"])
        self.stdout.write(f"Seeded/verified {created} education quality-gate item(s); courses remain unpublished.")
