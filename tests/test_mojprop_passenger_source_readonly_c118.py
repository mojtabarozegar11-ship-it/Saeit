"""C118 Passenger owner-only source identity: pure, bounded, no host contact."""
import ast
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from scripts.mojprop_passenger_source_readonly_c118 import (
    MAX_ENTRY_BYTES, STAGE_LITERAL, SOURCE_FILES,
    _owned_safe_file, source_code_signals,
)


class PassengerIdentityC118Tests(unittest.TestCase):
    def test_real_staging_literal_and_application_binding_signals(self):
        body = (
            "import sys\n"
            "sys.path.insert(0, '/home/zomorod2/Saeit-staging')\n"
            "from config.wsgi import application\n"
        ).encode()
        r = source_code_signals(body)
        self.assertTrue(r["entry_ast_parsed"])
        self.assertTrue(r["application_binding_declaration_found"])
        self.assertTrue(r["staging_path_literal_found"])
        self.assertEqual(r["entry_sha256"], hashlib.sha256(body).hexdigest())

    def test_comment_text_does_not_spoof_staging_literal(self):
        body = b"# /home/zomorod2/Saeit-staging\napplication = None\n"
        r = source_code_signals(body)
        self.assertFalse(r["staging_path_literal_found"])
        self.assertTrue(r["application_binding_declaration_found"])

    def test_quoted_user_supplied_text_is_not_a_runtime_worker_proof(self):
        body = ("description = '/home/zomorod2/Saeit-staging'\n"
                "other_name = 5\n").encode()
        r = source_code_signals(body)
        self.assertTrue(r["staging_path_literal_found"])
        self.assertFalse(r["application_binding_declaration_found"])
        self.assertNotIn("runtime_worker_identity_proven", r)

    def test_bound_source_rejects_empty_large_non_utf8_invalid_code(self):
        for bad in (b"", b"x"*(MAX_ENTRY_BYTES + 1), b"\xff",
                    b"def broken(:\n", b"["*1500+b"]"*1500, "abc", None):
            with self.subTest(kind=str(type(bad)), head=str(bad)[:10]):
                with self.assertRaises(ValueError):
                    source_code_signals(bad)

    def test_owner_fixed_file_regular_and_symlink_denial(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            f = root / "passenger_wsgi.py"
            f.write_text("application=None")
            f.chmod(0o600)
            self.assertEqual(_owned_safe_file(f, root=root), "present")
            f.chmod(0o606)
            self.assertEqual(_owned_safe_file(f, root=root), "unsafe")
            f.unlink()
            self.assertEqual(_owned_safe_file(f, root=root), "missing")
            outside = root / "untouched"
            outside.write_bytes(b"private")
            f.symlink_to(outside)
            self.assertEqual(_owned_safe_file(f, root=root), "unsafe")

    def test_nested_symlink_to_foreign_tree_never_followed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = root / "other"
            target.mkdir()
            (target / "private.py").write_bytes(b"secret")
            (root / "core").symlink_to(target, target_is_directory=True)
            self.assertEqual(_owned_safe_file(root / "core" / "private.py", root=root),
                             "unsafe")

    def test_writable_intermediate_dir_blocks_source_identity(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            subdir = root / "core"
            subdir.mkdir()
            file = subdir / "views.py"
            file.write_text("application = None")
            file.chmod(0o600)
            self.assertEqual(_owned_safe_file(file, root=root), "present")
            subdir.chmod(0o777)
            self.assertEqual(_owned_safe_file(file, root=root), "unsafe")
            subdir.chmod(0o700)

    def test_writable_root_blocks_even_readonly_module(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            file = root / "passenger_wsgi.py"
            file.write_text("application = None")
            file.chmod(0o600)
            self.assertEqual(_owned_safe_file(file, root=root), "present")
            root.chmod(0o777)
            self.assertEqual(_owned_safe_file(file, root=root), "unsafe")
            root.chmod(0o700)

    def test_hardlinked_entrypoint_does_not_prove_identity(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            file = root / "passenger_wsgi.py"
            file.write_text("application = None")
            file.chmod(0o600)
            self.assertEqual(_owned_safe_file(file, root=root), "present")
            alias = root / "alias.py"
            os.link(file, alias)
            self.assertEqual(_owned_safe_file(file, root=root), "unsafe")
            alias.unlink()
            self.assertEqual(_owned_safe_file(file, root=root), "present")

    def test_unsupported_path_outside_root_is_not_scanned(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "root"
            root.mkdir()
            foreign = Path(d) / "secret"
            foreign.write_text("dont read")
            self.assertEqual(_owned_safe_file(foreign, root=root), "unsafe")

    def test_fixed_five_source_names_and_no_payments_or_upload_calls(self):
        self.assertEqual(len(SOURCE_FILES), 5)
        self.assertEqual(set(SOURCE_FILES), {
            "core/mojprop_views.py",
            "core/mojprop_receipts.py",
            "core/mojprop_accessible_intake.py",
            "config/urls.py",
            "core/management/commands/mojprop_sales_action_queue.py",
        })
        file = Path(__file__).resolve().parents[1] / "scripts/mojprop_passenger_source_readonly_c118.py"
        tree = ast.parse(file.read_text())
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module)
        for banned in ("django", "subprocess", "requests", "socket", "urllib",
                       "sqlite3", "pymysql", "shutil"):
            self.assertNotIn(banned, imports)
        self.assertIn("runtime_worker_identity_proven\": False", file.read_text())
