#!/usr/bin/env python3
"""Offline regression checks for the read-only Passenger DB identity probe.

Only three pure helper functions are extracted from the workflow. No SSH,
production filesystem, process environment, or database is accessed here.
"""
import ast
import os
import pathlib
import tempfile
import textwrap
import unittest

WORKFLOW = pathlib.Path(__file__).resolve().parents[1] / ".github/workflows/zomorod-passenger-db-identity-readonly-20261031.yml"
START = '          PYTHONDONTWRITEBYTECODE=1 "$py" -B - <<\'PY\'\n'
END = "\n          PY\n"
HELPERS = {"secure_db_path", "is_passenger_candidate", "database_url_category"}


def source_and_helpers():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert workflow.count(START) == 1, "one bounded remote Python probe required"
    remote_python = textwrap.dedent(workflow.split(START, 1)[1].split(END, 1)[0])
    syntax = ast.parse(remote_python, filename=str(WORKFLOW))
    functions = [node for node in syntax.body if isinstance(node, ast.FunctionDef) and node.name in HELPERS]
    assert {node.name for node in functions} == HELPERS, "missing safe probe helper"
    namespace = {"os": os, "pathlib": pathlib}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(WORKFLOW), "exec"), namespace)
    return workflow, namespace


class ReadOnlyProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow, cls.fn = source_and_helpers()

    def test_normal_relative_database_path(self):
        with tempfile.TemporaryDirectory() as td:
            app = pathlib.Path(td) / "app"
            app.mkdir()
            expected = app / "db.sqlite3"
            self.assertEqual(self.fn["secure_db_path"]("db.sqlite3", app), expected)

    def test_normal_absolute_database_path(self):
        with tempfile.TemporaryDirectory() as td:
            app = pathlib.Path(td)
            expected = app / "db.sqlite3"
            self.assertEqual(self.fn["secure_db_path"](str(expected), app), expected)

    def test_final_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            app = pathlib.Path(td)
            real = app / "real.sqlite3"
            real.touch()
            (app / "db.sqlite3").symlink_to(real)
            self.assertIsNone(self.fn["secure_db_path"]("db.sqlite3", app))

    def test_parent_directory_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            app = pathlib.Path(td)
            real = app / "real"
            real.mkdir()
            (app / "link").symlink_to(real, target_is_directory=True)
            self.assertIsNone(self.fn["secure_db_path"]("link/db.sqlite3", app))

    def test_passenger_process_title_is_only_a_candidate(self):
        check = self.fn["is_passenger_candidate"]
        self.assertTrue(check(b"Passenger AppPreloader: /home/zomorod2/Saeit\0"))
        self.assertTrue(check(b"/venv/python\0/home/zomorod2/Saeit/passenger_wsgi.py\0"))
        self.assertFalse(check(b"/bin/bash\0-se\0"))
        self.assertFalse(check(b"/venv/python\0-B\0-\0"))

    def test_dburl_is_classified_without_disclosing_value(self):
        classify = self.fn["database_url_category"]
        fixtures = {
            b"PATH=/bin\0": "absent",
            b"DATABASE_URL=\0": "empty",
            b"DATABASE_URL=sqlite:////home/user/prod.sqlite3\0": "sqlite",
            b"DATABASE_URL=postgres://name:password@example.invalid/db\0": "other_scheme",
            b"DATABASE_URL=relative-filename\0": "unrecognized",
            b"DATABASE_URL=sqlite:///a\0DATABASE_URL=sqlite:///b\0": "ambiguous",
        }
        for blob, category in fixtures.items():
            with self.subTest(category=category):
                result = classify(blob)
                self.assertEqual(result, category)
                self.assertNotIn("password", result)
                self.assertNotIn("example.invalid", result)

    def test_release_remains_denied_and_readonly(self):
        workflow = self.workflow
        self.assertIn('print("PRODUCTION_PRIVATE_OFFICE_DEPLOY_ALLOWED=no")', workflow)
        self.assertIn('uri="file:"+quote(str(path),safe="/")+ "?mode=ro"', workflow)
        self.assertIn('conn.execute("PRAGMA query_only=ON")', workflow)
        self.assertIn("matching_fd>0", workflow)
        self.assertIn("stat.st_size>0", workflow)
        self.assertIn("PASSENGER_DB_PROBE_PATH_UNLINKED", workflow)

    def test_production_inspection_is_not_run_for_pull_requests(self):
        self.assertIn("if: github.event_name == 'push' && github.repository == 'mojtabarozegar11-ship-it/Saeit'", self.workflow)
        self.assertIn("    branches: [main]", self.workflow)
        self.assertIn('python3 scripts/test_zomorod_passenger_db_probe_source_20261031.py', self.workflow)


if __name__ == "__main__":
    unittest.main(verbosity=2)
