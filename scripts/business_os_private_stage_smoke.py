"""Offline, non-mutating smoke check for the private Business OS release bundle."""

import ast
import runpy
import sys
import subprocess
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))
    paths = sorted(
        list((root / "core").rglob("*.py"))
        + list((root / "command_center").rglob("*.py"))
    )
    paths += [root / "scripts" / "business_os_private_control.py",
              root / "scripts" / "business_os_vps_private_master_probe.py",
              root / "scripts" / "business_os_private_cron_verify.py"]
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
    factory_namespace = runpy.run_path(str(root / "tests" / "test_business_os_vps_factory_source.py"))
    factory_tests = [value for name, value in factory_namespace.items() if name.startswith("test_")]
    if len(factory_tests) < 3:
        raise RuntimeError("Expected factory observer source tests are missing")
    for test in factory_tests:
        test()
    private_ns = runpy.run_path(str(root / "tests" / "test_business_os_private_control.py"))
    private_tests = [value for name, value in private_ns.items() if name.startswith("test_")]
    if len(private_tests) < 8:
        raise RuntimeError("Expected private controller safety tests are missing")
    for test in private_tests:
        test()
    cycle_ns = runpy.run_path(str(root / "tests" / "test_business_os_private_cron_verify.py"))
    cycle_tests = [value for name, value in cycle_ns.items() if name.startswith("test_")]
    if len(cycle_tests) < 3:
        raise RuntimeError("Expected private recurring-cycle tests are missing")
    for test in cycle_tests:
        test()
    subprocess.run(["bash", "-n", str(root / "scripts" / "business_os_private_cron.sh")], check=True)
    print(f"BUSINESS_OS_PRIVATE_STAGE_OK ast_files={len(paths)} policy_tests={len(tests) + len(factory_tests) + len(private_tests) + len(cycle_tests)}")


if __name__ == "__main__":
    main()
