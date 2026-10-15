"""Static regression tests for the additive private evidence cron installer."""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"deploy"/"install_factory_research_monitor.sh"


class EvidenceMonitorInstallerTests(unittest.TestCase):
    def test_shell_is_valid(self):
        result=subprocess.run(["bash","-n",str(SCRIPT)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_hourly_is_scoped_and_rollbackable(self):
        s=SCRIPT.read_text(encoding="utf-8")
        for marker in ("SAEIT_FACTORY_RESEARCH_EVIDENCE_V1",
                       "crontab -l", "crontab \"$tmp\"",
                       "crontab \"$backup\"",
                       "FACTORY_MAIN_LOOP_ALIVE_PRE_MONITOR_CHANGE",
                       "FACTORY_MAIN_LOOP_ALIVE_POST_MONITOR_CHANGE",
                       "evidence-sidecar-candidate",
                       "research-evidence-sidecar",
                       "--limit 50", "43 * * * *"):
            self.assertIn(marker,s)
        for forbidden in ("systemctl restart","pkill","kill -9",
                          "sudo ","rm -rf","DROP TABLE","ALTER TABLE",
                          "sed -i /etc/crontab"):
            self.assertNotIn(forbidden,s)
        self.assertIn("install|remove",s)
        self.assertIn("status|install|remove",s)

if __name__=="__main__":
    unittest.main()
