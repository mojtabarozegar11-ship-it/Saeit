import unittest
import pathlib
from scripts.f01_owner_factory_quiesce_20261030 import (
    cron_is_factory, paused_cron, PAUSE_TAG, is_scoped_factory_process
)

class FactoryOwnerStopTests(unittest.TestCase):
    def test_only_marked_factory_cron_disabled(self):
        data = (
          "MAILTO=owner@example.invalid\n"
          "* * * * * /bin/bash /home/githubops/factory-runtime/tick.sh # SAEIT_FACTORY_EVERY_MINUTE_V1\n"
          "*/5 * * * * /usr/bin/true # unrelated\n"
          "* * * * * /usr/bin/echo factory news # not a production factory job\n"
        )
        changed,n=paused_cron(data)
        self.assertEqual(n,1)
        self.assertEqual(changed.count(PAUSE_TAG),1)
        self.assertIn("*/5 * * * * /usr/bin/true # unrelated\n",changed)
        self.assertIn("* * * * * /usr/bin/echo factory news # not a production factory job\n",changed)

    def test_env_comments_and_unrelated_factory_words_not_disabled(self):
        for line in ("# * * * * * factory","", "FACTORY_ENV=hello",
                     "   # /factory-runtime/batch",
                     "* * * * * /usr/bin/echo factory"):
            self.assertFalse(cron_is_factory(line))

    def test_scoped_cron_marker_and_path(self):
        self.assertTrue(cron_is_factory(
            "* * * * * /bin/bash /home/githubops/factory-runtime/operations/run.sh"))
        self.assertTrue(cron_is_factory(
            "* * * * * /bin/bash /unknown/dispatch # SAEIT_FACTORY_LIFECYCLE_12_V1"))

    def test_idempotent_disabled_line(self):
        orig="* * * * * /home/githubops/factory-runtime/tick\n"
        once,n=paused_cron(orig)
        twice,m=paused_cron(once)
        self.assertEqual(n,1)
        self.assertEqual(m,0)
        self.assertEqual(once,twice)

    def test_only_exact_owned_factory_worker(self):
        self.assertTrue(is_scoped_factory_process(
            b"/usr/bin/python3\0-B\0/home/githubops/factory-runtime/operations/worker.py\0"))
        self.assertTrue(is_scoped_factory_process(
            b"/bin/bash\0/home/githubops/factory-runtime/operations/tick.sh\0"))

    def test_unrelated_processes_never_selected(self):
        bad=[
            b"/usr/bin/python3\0-x\0/other/factory_worker.py\0",
            b"/bin/bash\0-c\0python /home/githubops/factory-runtime/x.py\0",
            b"/usr/bin/ssh\0host\0/home/githubops/factory-runtime/x.py\0",
            b"/usr/bin/rsync\0/home/githubops/factory-runtime/data\0other\0",
            b"/usr/bin/scp\0/home/githubops/factory-runtime/data\0host:/backup\0",
            b"/usr/bin/python3\0/home/githubops/factory-runtimeevil/f.py\0",
            b"/usr/bin/python3\0factory\0",
            b"",
        ]
        for args in bad:
            with self.subTest(argv=args):
                self.assertFalse(is_scoped_factory_process(args))

    def test_no_force_kill_and_no_full_stop_claim(self):
        source=pathlib.Path(__file__).resolve().parents[1]/"scripts"/"f01_owner_factory_quiesce_20261030.py"
        text=source.read_text()
        self.assertNotIn("signal.SIGKILL",text)
        self.assertIn('"full_factory_stop_verified":False',text)
        self.assertIn('"system_level_timers_verified":False',text)
        self.assertNotIn("kids={p for p,item",text)

if __name__ == "__main__":
    unittest.main()
