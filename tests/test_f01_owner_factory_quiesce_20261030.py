import unittest
from scripts.f01_owner_factory_quiesce_20261030 import cron_is_factory,paused_cron,PAUSE_TAG
class FactoryOwnerStopTests(unittest.TestCase):
    def test_pauses_scoped_factory_only(self):
        data="MAILTO=owner@example.invalid\n* * * * * /bin/bash /home/githubops/factory-runtime/tick.sh # SAEIT_FACTORY\n*/5 * * * * /usr/bin/true # unrelated\n"
        altered,n=paused_cron(data)
        self.assertEqual(n,1)
        self.assertTrue(altered.startswith("MAILTO=owner@example.invalid\n"+PAUSE_TAG))
        self.assertTrue(altered.endswith("*/5 * * * * /usr/bin/true # unrelated\n"))
    def test_ignores_comments_and_env(self):
        for row in ("# * * * * * factory","", "FACTORY_ENV=hello",
                    "   # /factory-runtime/batch"):
            self.assertFalse(cron_is_factory(row))
    def test_known_master_agent(self):
        self.assertTrue(cron_is_factory("* * * * * /x/master-agent/dispatch"))
    def test_idempotent_disabled_line(self):
        orig="* * * * * /x/factory-runtime/tick\n"
        once,n=paused_cron(orig)
        twice,m=paused_cron(once)
        self.assertEqual(n,1);self.assertEqual(m,0)
        self.assertEqual(once,twice)
if __name__=="__main__":
    unittest.main()
