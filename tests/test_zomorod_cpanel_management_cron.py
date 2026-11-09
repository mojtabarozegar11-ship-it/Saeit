"""Offline regression checks for the draft cPanel cron evidence probe."""
import datetime as dt
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "zomorod_cpanel_cron_evidence_readonly.py"
if not MODULE_PATH.is_file():
    MODULE_PATH = Path(__file__).with_name("zomorod_cpanel_cron_evidence_readonly.py")
module_spec = importlib.util.spec_from_file_location("zomorod_cpanel_probe", MODULE_PATH)
target = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(target)


class ManagementProbeTest(unittest.TestCase):
    def setUp(self):
        self.entry = ("17 */6 * * * " + target.MANAGEMENT_COMMAND +
                      " # " + target.MANAGEMENT_MARKER)

    def test_installed_once(self):
        self.assertEqual(target._management_cron_state((self.entry,)), "CONFIGURED_ONCE")

    def test_missing(self):
        self.assertEqual(target._management_cron_state(tuple()), "ABSENT")

    def test_duplicate(self):
        self.assertEqual(target._management_cron_state((self.entry, self.entry)), "DUPLICATE")

    def test_wrong_schedule(self):
        self.assertEqual(target._management_cron_state((self.entry.replace("17 */6", "18 */6"),)),
                         "SCHEDULE_MISMATCH")

    def test_wrong_log_destination(self):
        self.assertEqual(target._management_cron_state((self.entry.replace("command-scan-cron.log", "another.log"),)),
                         "COMMAND_MISMATCH")

    def test_shell_command_lookalike(self):
        self.assertEqual(target._management_cron_state((self.entry.replace("/usr/local/bin/php", "echo /usr/local/bin/php"),)),
                         "COMMAND_MISMATCH")

    def test_comment_only_excluded(self):
        self.assertEqual(target.summarize_cron("# " + self.entry)["MANAGEMENT_COMMAND_CRON"], "ABSENT")

    def test_exact_result_never_claims_execution(self):
        result = target.summarize_cron(self.entry)
        self.assertEqual(result["MANAGEMENT_COMMAND_CRON"], "CONFIGURED_ONCE")
        self.assertEqual(result["MANAGEMENT_CRON_EXECUTION_PROVEN"], "NO")
        self.assertEqual(result["MANAGEMENT_CRON_TIMEZONE_VERIFIED"], "NO")

    def test_oversized_readback_fails_closed(self):
        self.assertEqual(target.summarize_cron("x" * (target.MAX_CRON_CHARS + 1)),
                         {"READBACK": "UNVERIFIED"})

    def _inspect(self, data, age_minutes=0, symlink=False):
        with tempfile.TemporaryDirectory() as root:
            log = Path(root) / "worker.log"
            log.write_bytes(data)
            stamp = dt.datetime.now(dt.timezone.utc).timestamp() - age_minutes * 60
            os.utime(log, (stamp, stamp))
            if symlink:
                link = Path(root) / "link.log"
                link.symlink_to(log)
                log = link
            with patch.object(target, "MANAGEMENT_LOG", log):
                return target._management_log_state()

    def test_recent_complete_success_is_output_only(self):
        self.assertEqual(self._inspect(b'{"status":"ok"}\n'), "RECENT_OK_OUTPUT")

    def test_incomplete_log_is_rejected(self):
        self.assertEqual(self._inspect(b'{"status":"ok"}'), "PARTIAL_OR_EMPTY")

    def test_last_error_overrides_old_success(self):
        self.assertEqual(self._inspect(b'{"status":"ok"}\n{"status":"error"}\n'),
                         "RECENT_UNCLASSIFIED")

    def test_symlink_not_followed(self):
        self.assertEqual(self._inspect(b'{"status":"ok"}\n', symlink=True), "NONREGULAR")

    def test_stale_log(self):
        self.assertEqual(self._inspect(b'{"status":"ok"}\n', age_minutes=24 * 60), "STALE")

    def test_secret_log_content_not_in_summary(self):
        secret = "NEVER_EXPOSE_PASSWORD"
        self.assertEqual(self._inspect(('{' + '"status":"ok","pw":"' + secret + '"}\n').encode()),
                         "RECENT_OK_OUTPUT")
        self.assertNotIn(secret, repr(target.summarize_cron(self.entry)))


if __name__ == "__main__":
    unittest.main()
