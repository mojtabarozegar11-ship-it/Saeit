from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from uuid import uuid4

from .models import (
    EducationTrack, EducationCourse, EducationResource, EducationLesson,
    EducationEnrollment, EducationProgress, EducationBookmark,
    EducationAssessment, EducationQuestion, EducationAttempt, EducationCertificate,
)


def academy(request):
    # Data-first curriculum registry. Future Master Agent updates must follow
    # the project's owner-approval governance policy.
    tracks = [
        {"key": "school", "title": "مدرسه", "meta": "ابتدایی تا متوسطه", "text": "ریاضی، علوم، فارسی، زبان، مهارت‌های پایه و سواد دیجیتال با مسیر مرحله‌ای."},
        {"key": "konkur", "title": "کنکور", "meta": "متوسطه و کنکور", "text": "درس‌نامه، جزوه، تست، جمع‌بندی، آزمون و برنامه‌ریزی مطالعه برای مسیر کنکور."},
        {"key": "university", "title": "دانشگاه", "meta": "کارشناسی تا تحصیلات تکمیلی", "text": "دروس دانشگاهی، مهارت پژوهش، مقاله، داده، نرم‌افزار و آمادگی ورود به بازار کار."},
        {"key": "technical", "title": "فنی و حرفه‌ای", "meta": "مهارت و شغل", "text": "برنامه‌نویسی، هوش مصنوعی، طراحی، کسب‌وکار دیجیتال و مهارت‌های قابل درآمدزایی."},
        {"key": "agri", "title": "کشاورزی و تولید", "meta": "دانش تخصصی شرکت", "text": "کشت، باغداری، فرآوری، بسته‌بندی، کنترل کیفیت، زنجیره ارزش و بازار محصولات."},
        {"key": "industry", "title": "صنعت و زنجیره ارزش", "meta": "تولید تا بازار", "text": "توسعه محصول، تولید، عملیات، استاندارد، بسته‌بندی، فروش و مدیریت زنجیره."},
        {"key": "ai", "title": "هوش مصنوعی", "meta": "AI · Agents · Automation", "text": "مبانی هوش مصنوعی، عامل‌ها، اتوماسیون، طراحی سیستم و استفاده حرفه‌ای و مسئولانه."},
        {"key": "business", "title": "کسب‌وکار و درآمد", "meta": "Business · Commerce", "text": "بازاریابی، فروش، تجارت الکترونیک، برند، مالی و طراحی مدل درآمدی."},
    ]
    db_tracks = list(EducationTrack.objects.filter(active=True))
    if db_tracks:
        tracks = [{"key": x.key, "title": x.title, "meta": x.meta, "text": x.description} for x in db_tracks]
    course_q = request.GET.get("q", "").strip()
    track_key = request.GET.get("track", "").strip()
    access = request.GET.get("access", "").strip()
    course_qs = EducationCourse.objects.filter(active=True, approved=True).select_related("track")
    if course_q:
        from django.db.models import Q
        course_qs = course_qs.filter(Q(title__icontains=course_q) | Q(summary__icontains=course_q))
    if track_key:
        course_qs = course_qs.filter(track__key=track_key)
    if access == "free":
        course_qs = course_qs.filter(is_free=True)
    elif access == "paid":
        course_qs = course_qs.filter(is_free=False)
    courses = list(course_qs.order_by("track__sort_order", "title"))
    resources = [
        {"kind": "جزوه", "title": "کتابخانه جزوه‌های آموزشی", "text": "جزوه‌های سطح‌بندی‌شده، قابل مطالعه و قابل تکمیل برای هر مسیر.", "access": "رایگان محدود"},
        {"kind": "دوره", "title": "دوره‌های جامع مهارتی", "text": "درس‌نامه، ویدئو، تمرین، پروژه، آزمون و گواهی در مسیرهای منتخب.", "access": "رایگان + پولی"},
        {"kind": "آزمون", "title": "آزمون و ارزیابی", "text": "تمرین و سنجش مرحله‌ای برای شناسایی نقاط قوت و ضعف.", "access": "رایگان محدود"},
        {"kind": "پروژه", "title": "یادگیری پروژه‌محور", "text": "تبدیل آموخته‌ها به خروجی واقعی و نمونه‌کار قابل ارائه.", "access": "دوره‌های ویژه"},
    ]
    free_features = [
        "مطالعه بخشی از جزوه‌ها و درس‌نامه‌ها",
        "نمونه درس و تمرین محدود",
        "آزمون‌های منتخب و ارزیابی پایه",
        "مسیرهای پیشنهادی برای شروع یادگیری",
    ]
    paid_features = [
        "دوره کامل و فصل‌بندی‌شده",
        "جزوه و فایل‌های کامل آموزشی",
        "تمرین، پروژه و آزمون جامع",
        "گواهی، مسیر مهارتی و محتوای تخصصی",
    ]
    return render(request, "core/academy.html", {
        "tracks": tracks,
        "resources": resources,
        "courses": courses,
        "course_q": course_q, "track_key": track_key, "access": access,
        "free_features": free_features,
        "paid_features": paid_features,
    })


def education(request):
    """Canonical public entry point; /academy/ remains a compatibility URL."""
    return academy(request)


@login_required
def education_dashboard(request):
    enrollments = list(
        EducationEnrollment.objects.filter(user=request.user)
        .select_related("course", "course__track")
        .prefetch_related("progress", "course__lessons")
        .order_by("-updated_at")
    )
    cards = []
    for enrollment in enrollments:
        total = enrollment.course.lessons.filter(active=True).count()
        done = enrollment.progress.filter(completed=True).count()
        percent = round(done * 100 / total) if total else 0
        cards.append({"enrollment": enrollment, "total": total, "done": done, "percent": percent})
    certificates = EducationCertificate.objects.filter(enrollment__user=request.user).select_related("enrollment__course")
    attempts = EducationAttempt.objects.filter(user=request.user).select_related("assessment", "assessment__course").order_by("-submitted_at")[:20]
    certificate_course_ids = set(certificates.values_list("enrollment__course_id", flat=True))
    for card in cards:
        card["certificate_available"] = (
            card["enrollment"].status == "completed"
            and card["enrollment"].course_id not in certificate_course_ids
        )
    bookmarks = EducationBookmark.objects.filter(user=request.user).select_related("lesson", "lesson__course").order_by("-created_at")[:20]
    return render(request, "core/education_dashboard.html", {
        "cards": cards, "certificates": certificates, "attempts": attempts, "bookmarks": bookmarks,
    })


def education_course_detail(request, slug):
    course = get_object_or_404(
        EducationCourse.objects.select_related("track", "product").prefetch_related("lessons", "resources"),
        slug=slug,
        active=True,
        approved=True,
    )
    lessons = list(course.lessons.filter(active=True))
    resources = course.resources.filter(active=True, approved=True)
    assessments = course.assessments.filter(active=True, approved=True).prefetch_related("questions")
    enrollment = None
    progress_map = {}
    bookmarked = False
    if request.user.is_authenticated:
        enrollment = EducationEnrollment.objects.filter(course=course, user=request.user, status="active").first()
        if enrollment:
            progress_map = {p.lesson_id: p for p in enrollment.progress.all()}
        bookmarked = EducationBookmark.objects.filter(user=request.user, lesson=lesson).exists()
    lesson_rows = [{"lesson": lesson, "progress": progress_map.get(lesson.id)} for lesson in lessons]
    return render(request, "core/education_course_detail.html", {
        "course": course,
        "lessons": lessons,
        "lesson_rows": lesson_rows,
        "resources": resources,
        "enrollment": enrollment,
        "progress_map": progress_map,
        "assessments": assessments,
    })


@login_required
def education_enroll(request, slug):
    if request.method != "POST":
        raise Http404
    course = get_object_or_404(EducationCourse, slug=slug, active=True, approved=True)
    if not course.is_free:
        from .models import Order
        paid = Order.objects.filter(
            customer=request.user, status="paid",
            items__product=course.product,
        ).exists() if course.product_id else False
        if not paid:
            return JsonResponse({"ok": False, "error": "purchase_required"}, status=403)
        source = "purchase"
    else:
        source = "free"
    enrollment, created = EducationEnrollment.objects.get_or_create(
        course=course, user=request.user,
        defaults={"source": source},
    )
    return JsonResponse({"ok": True, "created": created, "enrollment_id": enrollment.pk})


def education_certificate(request, code):
    certificate = get_object_or_404(
        EducationCertificate.objects.select_related("enrollment__course"),
        code=code,
    )
    return render(request, "core/education_certificate.html", {"certificate": certificate})


@login_required
def education_issue_certificate(request, slug):
    if request.method != "POST":
        raise Http404
    course = get_object_or_404(EducationCourse, slug=slug, active=True, approved=True)
    enrollment = get_object_or_404(EducationEnrollment, course=course, user=request.user, status="completed")
    certificate, created = EducationCertificate.objects.get_or_create(
        enrollment=enrollment,
        defaults={
            "code": f"EDU-{course.pk}-{request.user.pk}-{uuid4().hex[:12].upper()}",
            "title": f"گواهی پایان دوره {course.title}",
            "verification_note": "این گواهی فقط برای دوره تکمیل‌شده صادر می‌شود.",
        },
    )
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "created": created, "code": certificate.code})
    return redirect("education_dashboard")


def education_lesson(request, slug, lesson_id):
    course = get_object_or_404(EducationCourse, slug=slug, active=True, approved=True)
    lesson = get_object_or_404(EducationLesson, pk=lesson_id, course=course, active=True)
    lessons = list(course.lessons.filter(active=True))
    position = next((i for i, item in enumerate(lessons) if item.id == lesson.id), 0)
    previous_lesson = lessons[position - 1] if position > 0 else None
    next_lesson = lessons[position + 1] if position + 1 < len(lessons) else None
    bookmarked = request.user.is_authenticated and EducationBookmark.objects.filter(user=request.user, lesson=lesson).exists()
    enrollment = EducationEnrollment.objects.filter(course=course, user=request.user, status="active").first()
    if not enrollment:
        if not (course.is_free and lesson.is_free_preview):
            return JsonResponse({"ok": False, "error": "enrollment_required"}, status=403)
        return render(request, "core/education_lesson.html", {"course": course, "lesson": lesson, "enrollment": None, "progress": None, "previous_lesson": previous_lesson, "next_lesson": next_lesson, "lesson_position": position + 1, "lesson_total": len(lessons), "bookmarked": bookmarked})
    progress, _ = EducationProgress.objects.get_or_create(enrollment=enrollment, lesson=lesson)
    return render(request, "core/education_lesson.html", {"course": course, "lesson": lesson, "enrollment": enrollment, "progress": progress, "previous_lesson": previous_lesson, "next_lesson": next_lesson, "lesson_position": position + 1, "lesson_total": len(lessons), "bookmarked": bookmarked})


@login_required
def education_lesson_complete(request, slug, lesson_id):
    if request.method != "POST":
        raise Http404
    course = get_object_or_404(EducationCourse, slug=slug, active=True, approved=True)
    lesson = get_object_or_404(EducationLesson, pk=lesson_id, course=course, active=True)
    enrollment = get_object_or_404(EducationEnrollment, course=course, user=request.user, status="active")
    progress, _ = EducationProgress.objects.get_or_create(enrollment=enrollment, lesson=lesson)
    progress.completed = True
    progress.progress_percent = 100
    progress.completed_at = timezone.now()
    progress.save()
    total = lesson.course.lessons.filter(active=True).count()
    done = enrollment.progress.filter(completed=True).count()
    if total and done >= total:
        enrollment.status = "completed"
        enrollment.completed_at = timezone.now()
        enrollment.save(update_fields=["status", "completed_at", "updated_at"])
    return JsonResponse({"ok": True, "completed_lessons": done, "total_lessons": total, "course_completed": enrollment.status == "completed"})


@login_required
def education_bookmark(request, slug, lesson_id):
    if request.method != "POST":
        raise Http404
    lesson = get_object_or_404(EducationLesson, pk=lesson_id, course__slug=slug, course__active=True, course__approved=True, active=True)
    bookmark = EducationBookmark.objects.filter(user=request.user, lesson=lesson).first()
    if bookmark:
        bookmark.delete()
        return JsonResponse({"ok": True, "created": False, "removed": True})
    bookmark = EducationBookmark.objects.create(user=request.user, lesson=lesson)
    return JsonResponse({"ok": True, "created": True, "removed": False, "bookmark_id": bookmark.pk})


@login_required
def education_assessment(request, slug, assessment_id):
    course = get_object_or_404(EducationCourse, slug=slug, active=True, approved=True)
    assessment = get_object_or_404(EducationAssessment, pk=assessment_id, course=course, active=True, approved=True)
    enrollment = EducationEnrollment.objects.filter(course=course, user=request.user).exclude(status="cancelled").first()
    if not enrollment:
        return JsonResponse({"ok": False, "error": "enrollment_required"}, status=403)
    questions = assessment.questions.all()
    return render(request, "core/education_assessment.html", {"course": course, "assessment": assessment, "questions": questions})


@login_required
def education_assessment_submit(request, slug, assessment_id):
    if request.method != "POST":
        raise Http404
    course = get_object_or_404(EducationCourse, slug=slug, active=True, approved=True)
    assessment = get_object_or_404(EducationAssessment, pk=assessment_id, course=course, active=True, approved=True)
    enrollment = EducationEnrollment.objects.filter(course=course, user=request.user).exclude(status="cancelled").first()
    if not enrollment:
        return JsonResponse({"ok": False, "error": "enrollment_required"}, status=403)
    questions = list(assessment.questions.all())
    answers = request.POST
    correct = sum(1 for q in questions if str(answers.get(f"q_{q.pk}", "")) == str(q.correct_index))
    score = round((correct / len(questions)) * 100) if questions else 0
    attempt = EducationAttempt.objects.create(
        assessment=assessment, user=request.user,
        answers={str(q.pk): answers.get(f"q_{q.pk}", "") for q in questions},
        score=score, passed=score >= assessment.passing_score,
    )
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "score": score, "passed": attempt.passed, "attempt_id": attempt.pk})
    return render(request, "core/education_assessment_result.html", {
        "course": course, "assessment": assessment, "attempt": attempt,
        "correct": correct, "total": len(questions),
    })
