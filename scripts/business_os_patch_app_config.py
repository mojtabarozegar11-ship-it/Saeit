"""Safely add a paid-order startup listener to varied cPanel CoreConfig layouts.

No changes in --check or --self-test. For --apply, atomically replace only
core/apps.py after AST-level semantic equivalence and Python compilation.
"""
import argparse
import ast
import os
from pathlib import Path
import tempfile


_READY = (
    "    def ready(self):\n"
    "        from . import purchase_signals  # noqa: F401\n"
)


def patched(source):
    original = ast.parse(source)
    classes = [n for n in original.body if isinstance(n, ast.ClassDef) and n.name == "CoreConfig"]
    if len(classes) != 1 or original.body[-1] is not classes[0]:
        raise ValueError("unexpected_app_config_structure")
    cls = classes[0]
    if len(cls.bases) != 1 or not isinstance(cls.bases[0], ast.Name) or cls.bases[0].id != "AppConfig":
        raise ValueError("unexpected_app_config_base")
    fields = {}
    for node in cls.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            raise ValueError("custom_app_config_body")
        if node.targets[0].id not in ("default_auto_field", "name"):
            raise ValueError("custom_app_config_field")
        fields[node.targets[0].id] = node.value
    if not isinstance(fields.get("name"), ast.Constant) or fields["name"].value != "core":
        raise ValueError("not_core_app")

    lines = source.splitlines(keepends=True)
    if cls.lineno == cls.end_lineno:
        # cPanel can ship a compact, one-line class suite. Appending an indented
        # method to that suite would cause IndentationError. Expand just that
        # class line while keeping each original assignment intact.
        original_line = lines[cls.lineno - 1].strip()
        if not original_line.startswith("class CoreConfig(AppConfig):"):
            raise ValueError("unexpected_compact_header")
        statements = [ast.get_source_segment(source, n) for n in cls.body]
        if any(not s or "\n" in s or "#" in s for s in statements):
            raise ValueError("unsafe_compact_body")
        compact = "class CoreConfig(AppConfig):\n" + "".join("    " + s.strip() + "\n" for s in statements)
        candidate = (
            "".join(lines[:cls.lineno - 1])
            + compact
            + _READY
            + "".join(lines[cls.end_lineno:])
        )
        shape = "compact_expanded"
    else:
        # Insert while still inside CoreConfig; never append after uninspected
        # top-level text or trailing comments.
        prior = "".join(lines[:cls.end_lineno])
        import re
        body_line = lines[cls.body[-1].lineno - 1]
        indent_match = re.match(r"^([ \t]+)", body_line)
        if not indent_match:
            raise ValueError("unsafe_multiline_indentation")
        indent = indent_match.group(1)
        next_indent = "\t" if indent.replace("\t", "") == "" else "    "
        ready = (
            indent + "def ready(self):\n"
            + indent + next_indent + "from . import purchase_signals  # noqa: F401\n"
        )
        candidate = prior + ("" if prior.endswith("\n") else "\n") + ready + "".join(lines[cls.end_lineno:])
        shape = "multiline_extended"
    compile(candidate, "<validated-app-config>", "exec")
    transformed = ast.parse(candidate)
    patched_class = next(n for n in transformed.body if isinstance(n, ast.ClassDef) and n.name == "CoreConfig")
    if len(patched_class.body) != len(cls.body) + 1:
        raise ValueError("unexpected_patch_length")
    new_method = patched_class.body.pop()
    if not isinstance(new_method, ast.FunctionDef) or new_method.name != "ready":
        raise ValueError("missing_ready_hook")
    if ast.dump(original, include_attributes=False) != ast.dump(transformed, include_attributes=False):
        raise ValueError("existing_semantics_changed")
    return candidate, shape


def self_test():
    for source in (
        "from django.apps import AppConfig\nclass CoreConfig(AppConfig): name = 'core'\n",
        "from django.apps import AppConfig\nclass CoreConfig(AppConfig): default_auto_field = 'django.db.models.BigAutoField'; name = 'core'\n",
        "from django.apps import AppConfig\n\nclass CoreConfig(AppConfig):\n    default_auto_field = 'django.db.models.BigAutoField'\n    name = 'core'\n",
        "from django.apps import AppConfig\nclass CoreConfig(AppConfig):\n        name = 'core'\n",
        "from django.apps import AppConfig\nclass CoreConfig(AppConfig):\n\tname = 'core'\n",
    ):
        output, _ = patched(source)
        assert "def ready(self)" in output
        compile(output, "<self-test>", "exec")
    for invalid in (
        "from django.apps import AppConfig\nclass CoreConfig(AppConfig): name = 'wrong'\n",
        "from django.apps import AppConfig\nclass CoreConfig(AppConfig):\n    name = 'core'\n    def ready(self): pass\n",
    ):
        try:
            patched(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid_existing_app_config_was_accepted")
    print("PURCHASE_APP_CONFIG_SELF_TEST_OK")


def main():
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--self-test", action="store_true")
    group.add_argument("--check", metavar="PATH")
    group.add_argument("--apply", metavar="PATH")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return
    path = Path(args.check or args.apply)
    if not path.is_file() or path.is_symlink():
        raise ValueError("unavailable_app_config")
    candidate, shape = patched(path.read_text(encoding="utf-8"))
    if args.check:
        print("PURCHASE_APP_CONFIG_CHECK_OK_" + shape.upper())
        return
    old_mode = path.stat().st_mode & 0o777
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix="apps.py.paid-listener-", delete=False,
        ) as stream:
            temp_path = Path(stream.name)
            stream.write(candidate)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_path, old_mode)
        os.replace(temp_path, path)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()
    print("PURCHASE_APP_CONFIG_APPLIED_" + shape.upper())


if __name__ == "__main__":
    try:
        main()
    except (ValueError, SyntaxError, OSError, AssertionError) as exc:
        reason = str(exc)
        safe_reasons = {
            "unexpected_app_config_structure", "unexpected_app_config_base",
            "custom_app_config_body", "custom_app_config_field", "not_core_app",
            "unexpected_compact_header", "unsafe_compact_body",
            "unexpected_patch_length", "missing_ready_hook",
            "existing_semantics_changed", "unavailable_app_config",
            "unsafe_multiline_indentation",
        }
        print("PURCHASE_APP_CONFIG_PATCH_REFUSED_" + (reason if reason in safe_reasons else type(exc).__name__))
        raise SystemExit(1)
