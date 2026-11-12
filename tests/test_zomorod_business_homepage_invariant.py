#!/usr/bin/env python3
"""No-network regression tests for public homepage invariance on guarded releases."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts/zomorod_business_homepage_invariant.sh"
INSTALLER = ROOT / "scripts/zomorod_business_genetics_guarded_install.sh"
WORKFLOW = ROOT / ".github/workflows/zomorod-business-update.yml"


def simulate(mode, operation, expected=None):
    with tempfile.TemporaryDirectory(prefix="zomorod-homepage-guard-") as tmp:
        fake_curl = Path(tmp) / "curl"
        counter = Path(tmp) / "counter"
        fake_curl.write_text(
            "#!/bin/sh\n"
            'n=0\n'
            'test ! -f "$FAKE_COUNTER" || n=$(cat "$FAKE_COUNTER")\n'
            'n=$((n+1))\n'
            'printf "%s" "$n" > "$FAKE_COUNTER"\n'
            'case "$FAKE_MODE" in\n'
            '  stable) printf HOME_FIXED ;;\n'
            '  varying) if test "$n" = 1; then printf HOME_FIXED; else printf HOME_DIFFERENT; fi ;;\n'
            '  inaccessible) exit 22 ;;\n'
            '  *) exit 2 ;;\n'
            'esac\n', encoding="utf-8",
        )
        fake_curl.chmod(0o700)
        env = dict(os.environ)
        env.update(
            PATH=tmp + os.pathsep + os.environ.get("PATH", ""),
            FAKE_MODE=mode,
            FAKE_COUNTER=str(counter),
        )
        return subprocess.run(
            ["bash", str(GUARD), operation] + ([expected] if expected is not None else []),
            capture_output=True, text=True, timeout=10, env=env,
        )


class HomepageInvariant(unittest.TestCase):
    def test_capture_requires_two_identical_https_responses(self):
        r = simulate("stable", "capture")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), hashlib.sha256(b"HOME_FIXED").hexdigest())
        r = simulate("varying", "capture")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("UNSTABLE_BASELINE_ABORT", r.stderr)

    def test_verify_refuses_changed_homepage(self):
        digest = hashlib.sha256(b"HOME_FIXED").hexdigest()
        ok = simulate("stable", "verify", digest)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn("PUBLIC_HOMEPAGE_HTML_UNCHANGED=VERIFIED", ok.stdout)
        bad = simulate("varying", "verify", digest)
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("CONTENT_CHANGED_ROLLBACK", bad.stderr)

    def test_fails_closed_on_unavailable_homepage_and_bad_hash(self):
        self.assertNotEqual(simulate("inaccessible", "capture").returncode, 0)
        self.assertNotEqual(simulate("stable", "verify", "NOT_A_SHA256").returncode, 0)

    def test_guard_uses_only_pinned_public_https_root(self):
        source = GUARD.read_text(encoding="utf-8")
        self.assertIn("'https://zomorodmelal.ir/'", source)
        for option in ("--proto '=https'", "--proto-redir '=https'", "--fail", "--max-time 25"):
            self.assertIn(option, source)
        self.assertNotIn("--insecure", source)
        self.assertNotIn("--request POST", source)

    def test_installer_checks_homepage_before_after_and_retains_rollback(self):
        install = INSTALLER.read_text(encoding="utf-8")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        before = install.index('homepage_baseline="$(bash "$stage/homepage-guard.sh" capture)"')
        first_change = install.index('mv -f "$private/.genetics-center.new-')
        after = install.index('bash "$stage/homepage-guard.sh" verify "$homepage_baseline"')
        rollback_disable = install.index("trap - EXIT")
        self.assertLess(before, first_change)
        self.assertLess(first_change, after)
        self.assertLess(after, rollback_disable)
        self.assertIn("BUSINESS_GENETICS_ROLLBACK=restored", install)
        self.assertIn("cat > '$stage/homepage-guard.sh'", workflow)
        self.assertNotIn("cat > /home/zomorod2/public_html", workflow)
        self.assertNotIn('mv -f "$private/.app.new-', workflow)
        self.assertNotIn("  push:\n", workflow)


if __name__ == "__main__":
    unittest.main()
