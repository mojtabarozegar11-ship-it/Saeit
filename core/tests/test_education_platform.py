from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from core.education_quality import audit_course, publication_ready
from core.models import (
    EducationAssessment, EducationQuestion, EducationCourse, EducationEnrollment, EducationLesson,
    EducationPresentation, EducationProgress, EducationResource, EducationTrack,
    EducationCertificate, EducationBookmark, Order, OrderItem, Product,
)


class EducationPlatformTests(TestCase):
    def setUp(self):
        self.track = EducationTrack.objects.create(
            key="test-track", title="مسیر آزمایشی", description="آموزش آزمایشی", level="test"
        )
        self.course = EducationCourse.objects.create(
            track=self.track,
            title="دوره آزمایشی",
            slug="test-course",
            summary="شرح کامل دوره",
            syllabus=["مقدمه", "مبانی", "تمرین", "پروژه"],
            prerequisites="مبانی اولیه",
            outcome="توانایی اجرای پروژه",
            is_free=True,
            active=True,
            approved=True,
            quality_status="published",
        )

    def test_quality_gate_blocks_incomplete_course(self):
        result = audit_course(self.course)
        self.assertFalse(result.ready)
        self.assertFalse(publication_ready(self.course))
        self.assertIn("lessons", [k for k, ok in result.checks.items() if not ok])

    def test_quality_gate_accepts_complete_course(self):
        EducationLesson.objects.create(course=self.course, title="درس اول", active=True)
        EducationResource.objects.create(course=self.course, kind="جزوه", title="منبع اول", active=True, approved=True)
        EducationPresentation.objects.create(
            course=self.course, title="اسلاید تدریس", audience="teacher",
            slide_count=20, active=True, approved=True, quality_status="published",
        )
        self.assertTrue(audit_course(self.course).ready)
        self.assertTrue(publication_ready(self.course))

    def test_presentation_supports_teacher_professor_and_coach(self):
        for audience in ("teacher", "professor", "coach"):
            presentation = EducationPresentation.objects.create(
                course=self.course, title=f"اسلاید {audience}", audience=audience
            )
            self.assertEqual(presentation.audience, audience)

    def test_education_course_detail_is_public_only_when_approved(self):
        response = self.client.get("/education/course/test-course/")
        self.assertEqual(response.status_code, 200)
        self.course.approved = False
        self.course.save(update_fields=["approved"])
        response = self.client.get("/education/course/test-course/")
        self.assertEqual(response.status_code, 404)

    def test_education_audit_command_is_read_only(self):
        before = self.course.updated_at
        call_command("education_audit")
        self.course.refresh_from_db()
        self.assertEqual(self.course.updated_at, before)

    def test_dashboard_requires_login(self):
        response = self.client.get("/education/dashboard/")
        self.assertEqual(response.status_code, 302)

    def test_free_enrollment_and_progress(self):
        user = get_user_model().objects.create_user(username="learner", password="pass")
        self.client.force_login(user)
        response = self.client.post("/education/course/test-course/enroll/")
        self.assertEqual(response.status_code, 200)
        enrollment = EducationEnrollment.objects.get(course=self.course, user=user)
        lesson = EducationLesson.objects.create(course=self.course, title="درس", active=True, is_free_preview=True)
        response = self.client.post(f"/education/course/test-course/lesson/{lesson.pk}/complete/")
        self.assertEqual(response.status_code, 200)
        progress = EducationProgress.objects.get(enrollment=enrollment, lesson=lesson)
        self.assertTrue(progress.completed)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, "completed")

    def test_paid_course_requires_paid_order(self):
        user = get_user_model().objects.create_user(username="buyer", password="pass")
        product = Product.objects.create(title="محصول دوره", product_type="education", price=100, currency="IRR", active=True)
        self.course.is_free = False
        self.course.product = product
        self.course.save(update_fields=["is_free", "product"])
        self.client.force_login(user)
        response = self.client.post("/education/course/test-course/enroll/")
        self.assertEqual(response.status_code, 403)
        order = Order.objects.create(customer=user, status="paid", total=100, currency="IRR")
        OrderItem.objects.create(order=order, product=product, quantity=1, unit_price=100, currency="IRR")
        response = self.client.post("/education/course/test-course/enroll/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(EducationEnrollment.objects.filter(course=self.course, user=user, source="purchase").exists())

    def test_certificate_is_publicly_verifiable(self):
        user = get_user_model().objects.create_user(username="graduate", password="pass")
        enrollment = EducationEnrollment.objects.create(course=self.course, user=user, status="completed")
        EducationCertificate.objects.create(enrollment=enrollment, code="EDU-VERIFY-001", title="گواهی آزمایشی")
        response = self.client.get("/education/certificate/EDU-VERIFY-001/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "EDU-VERIFY-001")

    def test_assessment_requires_enrollment(self):
        user = get_user_model().objects.create_user(username="examiner", password="pass")
        assessment = EducationAssessment.objects.create(
            course=self.course, title="آزمون", active=True, approved=True
        )
        self.client.force_login(user)
        response = self.client.get(
            f"/education/course/test-course/assessment/{assessment.pk}/"
        )
        self.assertEqual(response.status_code, 403)

    def test_bookmark_toggles(self):
        user = get_user_model().objects.create_user(username="reader", password="pass")
        lesson = EducationLesson.objects.create(
            course=self.course, title="درس نشانک", active=True
        )
        EducationEnrollment.objects.create(course=self.course, user=user, status="active")
        self.client.force_login(user)
        url = f"/education/course/test-course/lesson/{lesson.pk}/bookmark/"
        first = self.client.post(url)
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()["created"])
        self.assertTrue(EducationBookmark.objects.filter(user=user, lesson=lesson).exists())
        second = self.client.post(url)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()["removed"])
        self.assertFalse(EducationBookmark.objects.filter(user=user, lesson=lesson).exists())
    def test_assessment_submission_renders_result_page(self):
        user = get_user_model().objects.create_user(username="result-user", password="pass")
        enrollment = EducationEnrollment.objects.create(course=self.course, user=user, status="active")
        assessment = EducationAssessment.objects.create(course=self.course, title="آزمون نتیجه", passing_score=50, active=True, approved=True)
        EducationQuestion.objects.create(assessment=assessment, prompt="دو بعلاوه دو؟", choices=["3", "4"], correct_index=1)
        self.client.force_login(user)
        response = self.client.post(f"/education/course/test-course/assessment/{assessment.pk}/submit/", {f"q_{assessment.questions.first().pk}": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "نتیجه آزمون")
        self.assertContains(response, "100٪")

    def test_certificate_issue_redirects_to_dashboard(self):
        user = get_user_model().objects.create_user(username="cert-user", password="pass")
        EducationEnrollment.objects.create(course=self.course, user=user, status="completed")
        self.client.force_login(user)
        response = self.client.post("/education/course/test-course/certificate/issue/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/education/dashboard/")
        self.assertEqual(EducationCertificate.objects.filter(enrollment__user=user).count(), 1)

    def test_education_catalog_filters_published_courses(self):
        second_track = EducationTrack.objects.create(key="second", title="مسیر دوم", description="دوم", level="test")
        EducationCourse.objects.create(track=second_track, title="دوره رایگان دوم", slug="second-free", summary="آموزش هوش مصنوعی", syllabus=["1", "2", "3", "4"], prerequisites="", outcome="مهارت", is_free=True, active=True, approved=True, quality_status="published")
        response = self.client.get("/education/?q=هوش+مصنوعی&access=free&track=second")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "دوره رایگان دوم")
        self.assertNotContains(response, "دوره آزمایشی")

    def test_quality_content_seed_keeps_courses_unpublished(self):
        school_track = EducationTrack.objects.create(key="school", title="مدرسه", description="مسیر مدرسه", level="test")
        self.course.track = school_track
        self.course.active = False
        self.course.approved = False
        self.course.quality_status = "draft"
        self.course.save(update_fields=["track", "active", "approved", "quality_status"])
        call_command("education_seed_quality_content")
        self.course.refresh_from_db()
        self.assertFalse(self.course.active)
        self.assertFalse(self.course.approved)
        self.assertEqual(self.course.quality_status, "draft")
        self.assertTrue(self.course.lessons.filter(active=True).exists())
        self.assertTrue(self.course.resources.filter(active=True, approved=True).exists())
        self.assertTrue(self.course.presentations.filter(active=True, approved=True).exists())

    def test_quality_content_seed_is_idempotent(self):
        call_command("education_seed_quality_content")
        first = (
            self.course.lessons.count(),
            self.course.resources.count(),
            self.course.presentations.count(),
        )
        call_command("education_seed_quality_content")
        second = (
            self.course.lessons.count(),
            self.course.resources.count(),
            self.course.presentations.count(),
        )
        self.assertEqual(first, second)

