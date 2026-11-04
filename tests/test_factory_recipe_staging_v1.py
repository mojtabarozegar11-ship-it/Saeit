"""Regression checks for the fail-closed F-01 recipe staging operation.

This reads the actual deploy workflow rather than testing a second copy of the
algorithm. It performs no SSH connection, cron installation or live deployment.
"""

import ast
import contextlib
import io
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github/workflows/vps-single-product-factory-activation.yml"
)


class RecipeStagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.python_source = textwrap.dedent(
            workflow.split("<<'COPY_RECIPE'\n", 1)[1]
            .split("\n          COPY_RECIPE", 1)[0]
        )
        ast.parse(cls.python_source)
        cls.shell_source = textwrap.dedent(workflow.split("        run: |\n", 1)[1])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.destination = self.root / "destination"
        self.source.mkdir()
        self.destination.mkdir()

    def copy(self):
        saved_argv = sys.argv
        sys.argv = ["COPY_RECIPE", str(self.source), str(self.destination)]
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                exec(
                    compile(self.python_source, "F01_COPY_RECIPE", "exec"),
                    {"__name__": "__main__"},
                )
        finally:
            sys.argv = saved_argv

    def two_files(self):
        (self.source / "calculator.py").write_text("original", encoding="utf-8")
        (self.source / "test_calculator.py").write_text("test", encoding="utf-8")

    def test_preserves_nested_paths_even_if_basenames_match(self):
        (self.source / "components" / "empty").mkdir(parents=True)
        self.two_files()
        (self.source / "components" / "calculator.py").write_text(
            "different", encoding="utf-8"
        )
        self.copy()
        self.assertEqual((self.destination / "calculator.py").read_text(), "original")
        self.assertEqual(
            (self.destination / "components" / "calculator.py").read_text(),
            "different",
        )
        self.assertTrue((self.destination / "components" / "empty").is_dir())
        self.assertEqual(
            stat.S_IMODE((self.destination / "calculator.py").stat().st_mode), 0o600
        )
        self.assertEqual(
            stat.S_IMODE((self.destination / "components").stat().st_mode), 0o700
        )

    def test_rejects_file_symlink(self):
        self.two_files()
        (self.source / "forged.txt").symlink_to(self.source / "calculator.py")
        with self.assertRaisesRegex(SystemExit, "F01_RECIPE_SYMLINK_OR_SPECIAL_FILE"):
            self.copy()

    def test_rejects_directory_symlink(self):
        self.two_files()
        (self.source / "forged").symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(SystemExit, "F01_RECIPE_SYMLINK_OR_SPECIAL_DIR"):
            self.copy()

    def test_rejects_special_fifo(self):
        self.two_files()
        os.mkfifo(self.source / "bad-pipe")
        with self.assertRaisesRegex(SystemExit, "F01_RECIPE_SYMLINK_OR_SPECIAL_FILE"):
            self.copy()

    def test_rejects_incomplete_tree(self):
        (self.source / "only.py").write_text("x", encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "F01_RECIPE_TREE_INCOMPLETE"):
            self.copy()

    def test_rejects_nonempty_target(self):
        self.two_files()
        (self.destination / "existing.txt").write_text("do not overwrite")
        with self.assertRaisesRegex(SystemExit, "F01_RECIPE_TREE_UNSAFE"):
            self.copy()
        self.assertEqual((self.destination / "existing.txt").read_text(), "do not overwrite")

    def test_workflow_bash_syntax(self):
        result = subprocess.run(
            ["bash", "-n"],
            input=self.shell_source,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
