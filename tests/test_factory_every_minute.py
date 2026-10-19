"""Verify factory's minute cadence is sequential, locked and never publishes."""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[1]
SCRIPT=REPO/"deploy"/"install_factory_every_minute.sh"
PROD=REPO/"deploy"/"install_autonomous_factory_products.sh"
STOCK=REPO/"deploy"/"install_production_warehouse.sh"

class FactoryMinuteCadenceTests(unittest.TestCase):
    def test_installers_shell_syntax(self):
        for path in (SCRIPT,PROD,STOCK):
            z=subprocess.run(["bash","-n",str(path)],capture_output=True,text=True,timeout=10)
            self.assertEqual(z.returncode,0,z.stderr)
    def test_sole_cron_minute_tick_is_ordered_and_protected(self):
        s=SCRIPT.read_text()
        self.assertIn('"* * * * * /bin/bash "+runner+',s)
        self.assertIn("SAEIT_AUTONOMOUS_PRODUCTS_V2",s)
        self.assertIn("SAEIT_PRODUCTION_WAREHOUSE_V1",s)
        self.assertIn("SAEIT_FACTORY_EVERY_MINUTE_V1",s)
        self.assertIn("flock -n 8 || exit 0",s)
        self.assertLess(s.index('run-local-cycle.sh" || mfg_rc='),s.index('run-warehouse.sh" || wh_rc='))
        self.assertIn('crontab - < "$backup/proposed.cron"',s)
        self.assertIn('FACTORY_MINUTE_SITE_TRANSFER=DISABLED',s)
        for x in ("curl ","wget ","rsync ","scp ","factory_store_sender","multisite_orchestrator"):
            self.assertNotIn(x,s[s.index("cat > \"$temp\" <<'SH'"):s.index("\nSH\n")])
    def test_old_reinstallers_preserve_minute_cadence(self):
        s=PROD.read_text()
        w=STOCK.read_text()
        self.assertIn('grep -q SAEIT_FACTORY_EVERY_MINUTE_V1',s)
        self.assertIn('grep -q SAEIT_FACTORY_EVERY_MINUTE_V1',w)
        self.assertIn('VPS_LOCAL_EVERY_MINUTE_PRESERVED',s)
        self.assertIn('VPS_LOCAL_EVERY_MINUTE_PRESERVED',w)
    def test_actual_runner_execution_order_no_website_activity(self):
        content=SCRIPT.read_text()
        match=re.search(r'cat > "\$temp" <<\x27SH\x27\n([\s\S]*?)\nSH\n',content)
        self.assertIsNotNone(match)
        runner=match.group(1)+"\n"
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            ops=home/"factory-runtime"/"operations"
            prod=ops/"autonomous-product-runtime"
            stock=ops/"production-warehouse"
            prod.mkdir(parents=True)
            stock.mkdir()
            for path,value in ((prod/"run-local-cycle.sh","MANUFACTURE_QA"),
                               (stock/"run-warehouse.sh","WAREHOUSE_STOCK")):
                path.write_text("#!/bin/bash\nprintf '%s\\n' '"+value+"' >> \"$HOME/events.log\"\n")
                path.chmod(0o700)
            worker=stock/"run-minute-cycle.sh"
            worker.write_text(runner)
            worker.chmod(0o700)
            env=dict(os.environ,HOME=td)
            p=subprocess.run(["bash",str(worker)],env=env,capture_output=True,text=True,timeout=20)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual((home/"events.log").read_text().splitlines(),
                             ["MANUFACTURE_QA","WAREHOUSE_STOCK"])
            output=(ops/"factory-minute-cycle.log").read_text()
            self.assertIn("FACTORY_MINUTE_MANUFACTURING_FINISHED=true",output)
            self.assertIn("FACTORY_MINUTE_WAREHOUSE_FINISHED=true",output)
    def test_failed_manufacture_cannot_prevent_existing_stock_scan(self):
        content=SCRIPT.read_text()
        script=re.search(r'cat > "\$temp" <<\x27SH\x27\n([\s\S]*?)\nSH\n',content).group(1)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            ops=root/"factory-runtime"/"operations"
            prod=ops/"autonomous-product-runtime"
            stock=ops/"production-warehouse"
            prod.mkdir(parents=True)
            stock.mkdir()
            (prod/"run-local-cycle.sh").write_text("#!/bin/bash\nexit 4\n")
            (stock/"run-warehouse.sh").write_text("#!/bin/bash\necho stocked > \"$HOME/warehouse_executed\"\n")
            worker=stock/"run-minute-cycle.sh"
            worker.write_text(script)
            e=dict(os.environ,HOME=td)
            p=subprocess.run(["bash",str(worker)],env=e,capture_output=True,text=True,timeout=20)
            self.assertNotEqual(p.returncode,0)
            self.assertTrue((root/"warehouse_executed").is_file())
            self.assertIn("FACTORY_MINUTE_MANUFACTURING_FAILED=4",
                          (ops/"factory-minute-cycle.log").read_text())

if __name__=="__main__":unittest.main()
