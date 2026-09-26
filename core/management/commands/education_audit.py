from django.core.management.base import BaseCommand

from core.education_quality import audit_course
from core.models import EducationCourse


class Command(BaseCommand):
    help = "Audit education courses without publishing or modifying them."

    def handle(self, *args, **options):
        courses = EducationCourse.objects.select_related("track").prefetch_related("lessons", "resources")
        if not courses.exists():
            self.stdout.write("No education courses found.")
            return
        ready_count = 0
        for course in courses:
            result = audit_course(course)
            if result.ready:
                ready_count += 1
            missing = [name for name, ok in result.checks.items() if not ok]
            state = "READY" if result.ready else "BLOCKED"
            suffix = "" if not missing else " | missing: " + ", ".join(missing)
            self.stdout.write(f"{state} | {course.slug} | {course.quality_status}{suffix}")
        self.stdout.write(f"Audited {courses.count()} course(s); {ready_count} ready for quality review.")
