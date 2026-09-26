from dataclasses import dataclass


REQUIRED_COURSE_FIELDS = (
    "summary",
    "syllabus",
    "prerequisites",
    "outcome",
)


@dataclass(frozen=True)
class EducationQualityResult:
    ready: bool
    checks: dict


def audit_course(course, lessons=None, resources=None):
    lessons = list(lessons if lessons is not None else course.lessons.filter(active=True))
    resources = list(resources if resources is not None else course.resources.filter(active=True, approved=True))
    checks = {
        "summary": bool(course.summary.strip()),
        "syllabus": isinstance(course.syllabus, list) and len(course.syllabus) >= 4,
        "prerequisites": bool(course.prerequisites.strip()),
        "outcome": bool(course.outcome.strip()),
        "lessons": len(lessons) >= 1,
        "resources": len(resources) >= 1,
        "pricing": bool(course.is_free or course.price > 0),
        "track": bool(course.track_id),
        "presentations": len(course.presentations.filter(active=True, approved=True)) >= 1,
    }
    return EducationQualityResult(ready=all(checks.values()), checks=checks)


def publication_ready(course, lessons=None, resources=None):
    result = audit_course(course, lessons=lessons, resources=resources)
    return bool(course.active and course.approved and result.ready)
