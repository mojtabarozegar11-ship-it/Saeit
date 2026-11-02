"""Fail-closed, no-host regression for the office release job's default deny.

This module only reads workflow source.  It does not import Django, open
network connections, access secrets, or execute any release commands.
"""
from pathlib import Path
import re
import sys
import unittest


WORKFLOW = Path(".github/workflows/zomorod-office-root-fallback-release-20261031.yml")
DENY = "$" + "{{ false }}"


def require_release_default_deny(source: str) -> None:
    """Reject absent, duplicated, nested, commented, or changed release guards."""
    lines = source.splitlines()
    jobs = [index for index, line in enumerate(lines) if line.strip() == "jobs:" and line == "jobs:"]
    if len(jobs) != 1:
        raise ValueError("OFFICE_JOBS_BLOCK_AMBIGUOUS")

    start = jobs[0] + 1
    end = next(
        (i for i in range(start, len(lines)) if re.match(r"^[A-Za-z_][A-Za-z0-9_-]*:", lines[i])),
        len(lines),
    )
    headers = []
    for i in range(start, end):
        match = re.fullmatch(r"  ([A-Za-z_][A-Za-z0-9_-]*):[ \t]*(?:#.*)?", lines[i])
        if match:
            headers.append((i, match.group(1)))
    releases = [i for i, (_, name) in enumerate(headers) if name == "release"]
    if len(releases) != 1:
        raise ValueError("OFFICE_RELEASE_JOB_AMBIGUOUS")
    index = releases[0]
    job_start = headers[index][0] + 1
    job_end = headers[index + 1][0] if index + 1 < len(headers) else end
    conditions = []
    for line in lines[job_start:job_end]:
        # Exactly job-level indentation; a step, comment, or shell string cannot count.
        if re.match(r"^    if[ \t]*:", line):
            conditions.append(line.split(":", 1)[1].strip())
    if conditions != [DENY]:
        raise ValueError("OFFICE_RELEASE_DEFAULT_DENY_MISSING_OR_AMBIGUOUS")


class ReadOnlyReleaseGateTests(unittest.TestCase):
    SAFE = (
        "name: office\n"
        "jobs:\n"
        "  validate:\n"
        "    runs-on: ubuntu-latest\n"
        "  release:\n"
        "    needs: validate\n"
        "    if: " + DENY + "\n"
        "    runs-on: ubuntu-latest\n"
    )

    def test_exact_job_guard_passes(self):
        require_release_default_deny(self.SAFE)

    def test_actual_workflow_is_denied(self):
        require_release_default_deny(WORKFLOW.read_text(encoding="utf-8"))

    def test_push_condition_denied(self):
        unsafe = self.SAFE.replace("    if: " + DENY, "    if: github.event_name == 'push'")
        with self.assertRaises(ValueError):
            require_release_default_deny(unsafe)

    def test_comment_is_not_guard(self):
        unsafe = self.SAFE.replace("    if: " + DENY, "    # if: " + DENY)
        with self.assertRaises(ValueError):
            require_release_default_deny(unsafe)

    def test_nested_step_condition_is_not_guard(self):
        unsafe = self.SAFE.replace("    if: " + DENY, "      if: " + DENY)
        with self.assertRaises(ValueError):
            require_release_default_deny(unsafe)

    def test_duplicate_conditions_denied(self):
        unsafe = self.SAFE.replace(
            "    if: " + DENY,
            "    if: github.event_name == 'push'\n    if: " + DENY,
        )
        with self.assertRaises(ValueError):
            require_release_default_deny(unsafe)

    def test_duplicate_release_jobs_denied(self):
        with self.assertRaises(ValueError):
            require_release_default_deny(self.SAFE + "  release:\n    if: github.event_name == 'push'\n")

    def test_guard_elsewhere_does_not_count(self):
        unsafe = self.SAFE.replace("    if: " + DENY, "    if: github.event_name == 'push'")
        unsafe += "  unrelated:\n    if: " + DENY + "\n"
        with self.assertRaises(ValueError):
            require_release_default_deny(unsafe)

    def test_missing_jobs_denied(self):
        with self.assertRaises(ValueError):
            require_release_default_deny("  release:\n    if: " + DENY + "\n")


if __name__ == "__main__":
    if sys.argv[1:] == ["--check"]:
        try:
            require_release_default_deny(WORKFLOW.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise SystemExit(str(error))
        print("OFFICE_RELEASE_DEFAULT_DENY=PASS_RELEASE_BLOCKED")
    else:
        unittest.main()
