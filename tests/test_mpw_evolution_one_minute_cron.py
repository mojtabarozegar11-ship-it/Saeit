"""Exact one-entry cPanel cron rescheduling regression checks; no remote effects."""
import unittest
from scripts.mpw_evolution_reschedule_one_minute_cpanel import (
    MARK, DEST, RUNTIME, cron_lines,
)

FLOCK = "/usr/bin/flock"
PY = "/usr/bin/python3"
TAIL = (f"{FLOCK} -n {RUNTIME}/cron.lock {PY} -B {DEST} --once "
        f"> {RUNTIME}/last_cycle.log 2>&1 {MARK}")
OLD = "59 * * * * " + TAIL
NEW = "* * * * * " + TAIL
BEFORE = "17 * * * * echo keep-master # MPW_V91_MAIN_ONLY_20261018\n"
AFTER = "37 * * * * echo keep-monitor # MPW_V11_MAIN_ONLY_SITE_HEALTH_20261018\n"


class ReschedulingTests(unittest.TestCase):
    def test_one_hourly_line_becomes_every_minute_and_every_other_byte_is_preserved(self):
        original = BEFORE + OLD + "\n" + AFTER
        target, is_minutely = cron_lines(original, FLOCK, PY)
        self.assertFalse(is_minutely)
        self.assertEqual(target, BEFORE + NEW + "\n" + AFTER)
        self.assertEqual(target.count(MARK), 1)

    def test_repeated_activation_is_noop(self):
        original = BEFORE + NEW + "\n" + AFTER
        target, is_minutely = cron_lines(original, FLOCK, PY)
        self.assertTrue(is_minutely)
        self.assertEqual(target, original)

    def test_all_other_cron_lines_preserved_with_comments_and_blanks(self):
        original = "# comment\\n\n" + BEFORE + "\n" + OLD + "\n" + AFTER
        target, _ = cron_lines(original, FLOCK, PY)
        self.assertEqual(target, original.replace(OLD, NEW))

    def test_unknown_private_command_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, "UNKNOWN_EVOLUTION_CRON_COMMAND"):
            cron_lines(BEFORE + OLD.replace(" --once", " --unsafe") + "\n", FLOCK, PY)

    def test_duplicate_marker_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, "EVOLUTION_CRON_NOT_UNIQUE"):
            cron_lines(BEFORE + OLD + "\n" + NEW + "\n", FLOCK, PY)

    def test_missing_marker_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, "EVOLUTION_CRON_NOT_UNIQUE"):
            cron_lines(BEFORE + AFTER, FLOCK, PY)


if __name__ == "__main__":
    unittest.main()
