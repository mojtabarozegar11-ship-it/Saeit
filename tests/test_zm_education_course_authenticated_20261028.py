"""Regression for the authenticated Zomorod Melal course detail page.

Run without Django or a database by executing the real view function AST with
read-only mock dependencies. In particular, an approved course with zero lessons
must not throw NameError when a customer is signed in.
"""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock

SOURCE = Path(__file__).resolve().parents[1] / "core" / "academy_views.py"


def load_view():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    fn = next(node for node in tree.body
              if isinstance(node, ast.FunctionDef) and node.name == "education_course_detail")
    isolated = ast.Module(body=[fn], type_ignores=[])
    course = SimpleNamespace(
        lessons=SimpleNamespace(filter=MagicMock(return_value=[])),
        resources=SimpleNamespace(filter=MagicMock(return_value=[])),
        assessments=SimpleNamespace(filter=MagicMock(
            return_value=SimpleNamespace(prefetch_related=MagicMock(return_value=[])))),
    )
    enrollment = SimpleNamespace(objects=SimpleNamespace(filter=MagicMock()))
    enrollment.objects.filter.return_value.first.return_value = None
    bookmarks = SimpleNamespace(objects=SimpleNamespace(filter=MagicMock()))
    scope = {
        "EducationCourse": SimpleNamespace(objects=MagicMock()),
        "EducationEnrollment": enrollment,
        "EducationBookmark": bookmarks,
        "get_object_or_404": MagicMock(return_value=course),
        "render": MagicMock(side_effect=lambda request, template, context: (template, context)),
    }
    exec(compile(isolated, str(SOURCE), "exec"), scope)
    return scope["education_course_detail"], course, scope, enrollment, bookmarks


class AuthenticatedCourseDetailRegression(TestCase):
    def test_signed_in_user_can_open_approved_course_without_lessons(self):
        view, course, scope, enrollment, bookmarks = load_view()
        request = SimpleNamespace(user=SimpleNamespace(is_authenticated=True))
        template, context = view(request, "approved-empty-course")
        self.assertEqual(template, "core/education_course_detail.html")
        self.assertIs(context["course"], course)
        self.assertEqual(context["lesson_rows"], [])
        self.assertEqual(context["progress_map"], {})
        enrollment.objects.filter.assert_called_once()
        bookmarks.objects.filter.assert_not_called()

    def test_signed_in_user_can_open_course_with_lessons_and_progress(self):
        view, course, scope, enrollment, bookmarks = load_view()
        first = SimpleNamespace(id=11)
        second = SimpleNamespace(id=12)
        course.lessons.filter.return_value = [first, second]
        enrollment.objects.filter.return_value.first.return_value = SimpleNamespace(
            progress=SimpleNamespace(all=MagicMock(return_value=[
                SimpleNamespace(lesson_id=11, completed=True)
            ]))
        )
        request = SimpleNamespace(user=SimpleNamespace(is_authenticated=True))
        template, context = view(request, "approved-course")
        self.assertEqual([x["lesson"].id for x in context["lesson_rows"]], [11, 12])
        self.assertTrue(context["lesson_rows"][0]["progress"].completed)
        self.assertIsNone(context["lesson_rows"][1]["progress"])
        bookmarks.objects.filter.assert_not_called()

    def test_anonymous_user_still_sees_public_course(self):
        view, course, scope, enrollment, bookmarks = load_view()
        request = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))
        template, context = view(request, "approved-course")
        self.assertEqual(template, "core/education_course_detail.html")
        self.assertIsNone(context["enrollment"])
        enrollment.objects.filter.assert_not_called()
        bookmarks.objects.filter.assert_not_called()


if __name__ == "__main__":
    import unittest
    unittest.main()
