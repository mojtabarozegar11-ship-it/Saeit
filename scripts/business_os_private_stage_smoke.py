"""Offline, non-mutating smoke check for the private Business OS release bundle."""

import ast
import runpy
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))
    paths = sorted(
        list((root / "core").rglob("*.py"))
        + list((root / "command_center").rglob("*.py"))
    )
    if not paths:
        raise RuntimeError("No management code to validate")
    for path in paths:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    namespace = runpy.run_path(str(root / "tests" / "test_business_management_review.py"))
    tests = [value for name, value in namespace.items() if name.startswith("test_")]
    if len(tests) < 5:
        raise RuntimeError("Expected evidence-policy smoke tests are missing")
    for test in tests:
        test()
    print(f"BUSINESS_OS_PRIVATE_STAGE_OK ast_files={len(paths)} policy_tests={len(tests)}")


if __name__ == "__main__":
    main()
