"""Real per-product queue rotation; no invented science, QA or store release."""
import fcntl
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from urllib.parse import unquote
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "sequential_casework", ROOT / "scripts/factory_sequential_scientific_casework_v1.py")
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def fixture(root, count=3):
    inbox = root / "production-instructions/stage-02/primary-fulltext-repair-inbox"
    inbox.mkdir(parents=True)
    for i in range(1, count+1):
        name = "WO-%08d--r001.json" % i
        tasks = [{"source_id":"S%d"%j,"doi":"10.1000/realstudy-%d"%j,
                  "required_action":"FETCH_LICENSABLE_PRIMARY_FULLTEXT_AND_CHECK_EXACT_PASSAGES",
                  "original_fulltext_retrieved":False,
                  "exact_supporting_pages_verified":False,
                  "linked_claim_ids":["C%d"%(j+1)]} for j in range(4)]
        claims = [{"claim_id":"C%d"%j,
                   "indexed_abstract_statement":
                   "Farming irrigation and evidence monitoring support controlled agricultural experimental observations in the field.",
                   "source_ids":["S%d"%((j-1)%4)]} for j in range(1,6)]
        packet = {"schema":"saeit.factory.scientific-source-repair.v1",
                  "order_file":name,"scientific_primary_source_tasks":tasks,
                  "scientific_claims":claims,"all_claims_verified":False,
                  "qc1000_approved":False,"public_distribution_allowed":False}
        (inbox/name).write_text(json.dumps(packet),encoding="utf-8")


def provider(url, limit):
    if "/search?" in url:
        doi = unquote(url.split("DOI%3A%22")[1].split("%22")[0]).lower()
        return json.dumps({"resultList":{"result":[{
            "doi":doi,"pmcid":"PMC123456"+doi[-1],"isRetracted":"N"}]}}).encode()
    digit = url.split("PMC123456")[1][0]
    doi = "10.1000/realstudy-"+digit
    para = ("Farming evidence and irrigation monitoring from peer reviewed "
            "agricultural experiments supports controlled field observations. "*12)
    body = "<p>"+para+"</p>"
    return ("<article xmlns:xlink='http://www.w3.org/1999/xlink'>"
            "<front><article-meta><article-id pub-id-type='doi'>"+doi+
            "</article-id><permissions><license xlink:href='https://creativecommons.org/licenses/by/4.0/'>"
            "Creative Commons</license></permissions></article-meta></front>"
            "<body>"+body*3+"</body></article>").encode()


def step_with_ample_disk(*args, **kwargs):
    """Isolate the science/rotation tests from the VPS's real disk level.

    A separate test below explicitly proves the 2 GiB production hold.
    """
    class Disk:
        free=worker.DISK_RESERVE + 1024 * 1024 * 1024
    with patch.object(worker.shutil, "disk_usage", return_value=Disk()):
        return worker.step(*args, **kwargs)


class SequentialCaseworkTests(unittest.TestCase):
    def test_pinned_order_repeats_without_rotating_other_products(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            fixture(root,3)
            selected="WO-00000002--r001.json"
            first=step_with_ample_disk(root,only_order_file=selected,http_get=provider)
            second=step_with_ample_disk(root,only_order_file=selected,http_get=provider)
            self.assertEqual(first["selected_order_file"],selected)
            self.assertEqual(second["selected_order_file"],selected)
            self.assertEqual(second["next_order_file"],selected)
            target=root/"production-instructions/stage-02/primary-source-acquisition-v1"
            self.assertFalse((target/".product-sequential-cursor.json").exists())
            self.assertEqual(len(list((target/"sequential-casework-v1").glob("*.json"))),1)

    def test_only_one_product_per_tick_with_real_evidence_and_review_hold(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            fixture(root)
            first=step_with_ample_disk(root,max_attempts=4,http_get=provider)
            self.assertEqual(first["cases_processed"],1)
            self.assertEqual(first["selected_order_file"],"WO-00000001--r001.json")
            self.assertEqual(first["result"],"WAITING_QUALIFIED_CLAIM_REVIEW_AND_REAUTHORING")
            self.assertEqual(first["source_attempts"],4)
            self.assertEqual(first["qc1000_approvals"],0)
            self.assertEqual(first["publications"],0)
            target=root/"production-instructions/stage-02/primary-source-acquisition-v1"
            self.assertEqual(len(list((target/"sequential-casework-v1").glob("*.json"))),1)
            second=step_with_ample_disk(root,http_get=lambda *_: (_ for _ in ()).throw(
                AssertionError("cached DOIs must not be fetched again")))
            self.assertEqual(second["selected_order_file"],"WO-00000002--r001.json")
            self.assertEqual(second["source_attempts"],0)
            third=step_with_ample_disk(root,http_get=provider)
            self.assertEqual(third["selected_order_file"],"WO-00000003--r001.json")
            next_tick=step_with_ample_disk(root,http_get=provider)
            self.assertEqual(next_tick["selected_order_file"],first["selected_order_file"])
            statuses=list((target/"sequential-casework-v1").glob("*.json"))
            self.assertEqual(len(statuses),3)
            self.assertTrue(all(json.loads(p.read_text())["qc1000_approved"] is False
                                for p in statuses))

    def test_corrupt_one_product_does_not_starve_next_or_change_original(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            fixture(root,2)
            p=root/"production-instructions/stage-02/primary-fulltext-repair-inbox/WO-00000001--r001.json"
            tampered=json.loads(p.read_text())
            tampered["qc1000_approved"]=True
            p.write_text(json.dumps(tampered))
            original=p.read_bytes()
            first=step_with_ample_disk(root,http_get=provider)
            self.assertEqual(first["result"],"BLOCKED_INPUT_INTEGRITY")
            self.assertEqual(first["qc1000_approvals"],0)
            self.assertEqual(original,p.read_bytes())
            second=step_with_ample_disk(root,http_get=provider)
            self.assertEqual(second["selected_order_file"],"WO-00000002--r001.json")
            self.assertEqual(second["result"],"WAITING_QUALIFIED_CLAIM_REVIEW_AND_REAUTHORING")

    def test_temporary_source_failure_keeps_product_blocked_but_rotates(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            fixture(root,2)
            m=worker.engine()
            def fail_once(url, limit):
                if "/search?" in url and "realstudy-0" in url:
                    raise m.TemporaryFailure("PROVIDER_500")
                return provider(url,limit)
            first=step_with_ample_disk(root,http_get=fail_once)
            self.assertEqual(first["result"],"SOURCE_OR_LICENSE_REWORK_REQUIRED")
            self.assertEqual(first["source_attempts"],4)
            second=step_with_ample_disk(root,http_get=provider)
            self.assertEqual(second["selected_order_file"],"WO-00000002--r001.json")
            self.assertEqual(second["result"],"WAITING_QUALIFIED_CLAIM_REVIEW_AND_REAUTHORING")
            third=step_with_ample_disk(root,http_get=provider)
            self.assertEqual(third["selected_order_file"],"WO-00000001--r001.json")
            self.assertEqual(third["result"],"WAITING_QUALIFIED_CLAIM_REVIEW_AND_REAUTHORING")

    def test_dry_run_is_no_write_and_contended_lock_is_safe(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            fixture(root,2)
            result=worker.step(root,dry_run=True)
            self.assertEqual(result["next_order_file"],"WO-00000001--r001.json")
            target=root/"production-instructions/stage-02/primary-source-acquisition-v1"
            self.assertFalse(target.exists())
            target.mkdir()
            with (target/".primary-acquisition.lock").open("a+b") as hold:
                fcntl.flock(hold.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
                locked=worker.step(root,http_get=provider)
                self.assertTrue(locked["already_running"])
                self.assertEqual(locked["cases_processed"],0)
                self.assertFalse((target/".product-sequential-cursor.json").exists())

    def test_low_disk_only_triages_and_never_fetches_more_xml(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            fixture(root,2)
            class Disk:
                free=1024 * 1024 * 1024
            with patch.object(worker.shutil, "disk_usage", return_value=Disk()):
                result=worker.step(root,http_get=lambda *_: (_ for _ in ()).throw(
                    AssertionError("must not fetch under storage reserve")))
            self.assertTrue(result["storage_reserve_hold"])
            self.assertEqual(result["source_attempts"],0)
            self.assertEqual(result["result"],"STORAGE_RESERVE_HOLD_WITH_SOURCE_REWORK_PENDING")
            self.assertEqual(result["qc1000_approvals"],0)


class CronInstallerPreflightTests(unittest.TestCase):
    """Test the actual installer preflight in isolation, never touching crontab."""

    def test_install_does_not_work_a_product_before_cron_audit(self):
        script = (ROOT / "deploy/install_factory_sequential_scientific_casework_v1.sh").read_text()
        self.assertLess(script.index('python3 - "$cron_backup"'),
                        script.index('install_checked "$source_engine"'))
        self.assertNotIn('timeout 90s "$py" -B "$case_worker" --factory-private', script)
        self.assertIn('flock -w 20 9', script)
        self.assertIn('systemctl list-timers --all', script)
        self.assertIn('CASEWORK_CONCURRENT_CRON_EDIT', script)
        self.assertIn('/usr/bin/flock -n', script)
        self.assertIn('CRON_CONFIGURED_NOT_QC1000', script)
        syntax = subprocess.run(["bash", "-n", str(ROOT / "deploy/install_factory_sequential_scientific_casework_v1.sh")],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(syntax.returncode, 0, syntax.stderr)

    def test_competing_minute_scheduler_is_rejected_before_any_product_work(self):
        script = (ROOT / "deploy/install_factory_sequential_scientific_casework_v1.sh").read_text()
        match = re.search(
            r'python3 - "\$cron_backup" "\$old_marker" "\$new_marker" "\$case_worker" <<\x27PY\x27\n([\s\S]*?)\nPY\n',
            script)
        self.assertIsNotNone(match)
        preflight = match.group(1)
        old = "SAEIT_LICENSED_PRIMARY_SOURCE_ACQUISITION_20261024"
        new = "SAEIT_SEQUENTIAL_SCIENCE_CASEWORK_20261025"
        worker = "/opt/production-instructions/sequential-scientific-casework-v1.py"
        old_row = f"* * * * * /usr/bin/python3 /opt/license-safe-primary-fulltext-acquisition.py # {old}"
        new_row = f"* * * * * /usr/bin/flock -n /tmp/lock /usr/bin/python3 {worker} # {new}"
        other = "*/5 * * * * /bin/bash /opt/owner500/runner.sh # SAEIT_OWNER500_AUTONOMOUS_F28_V1"
        cases = [
            ("", True, "PREFLIGHT_PASS"),
            (other, True, "PREFLIGHT_PASS"),
            (old_row, True, "PREFLIGHT_PASS"),
            (new_row, True, "PREFLIGHT_PASS"),
            ("# " + "* * * * * /bin/bash /opt/run-minute-cycle.sh", True, "PREFLIGHT_PASS"),
            (f"* * * * * /bin/bash /opt/run-minute-cycle.sh # SAEIT_FACTORY_EVERY_MINUTE_V1",
             False, "COMPETING_MINUTE_PIPELINE"),
            (f"* * * * * python3 /opt/agri200-autonomous-closed-loop.py # SAEIT_AGRI200_AUTONOMOUS_CLOSED_LOOP_V1",
             False, "COMPETING_MINUTE_PIPELINE"),
            ("* * * * * python3 /opt/custom-factory-cycle.py", False, "COMPETING_MINUTE_PIPELINE"),
            (new_row + "\n" + new_row, False, "DUPLICATE_OR_CONFLICTING_MARKERS"),
            (new_row + "\n" + old_row, False, "DUPLICATE_OR_CONFLICTING_MARKERS"),
            (old_row.replace("* * * * *", "*/5 * * * *"), False, "UNRECOGNIZED_OLD_SCHEDULER"),
            (new_row.replace(worker, "/opt/untrusted.py"), False, "UNRECOGNIZED_NEW_SCHEDULER"),
        ]
        with tempfile.TemporaryDirectory() as d:
            cron = Path(d) / "prior.cron"
            for value, allowed, message in cases:
                with self.subTest(cron=value):
                    cron.write_text(value + "\n")
                    outcome = subprocess.run(
                        [sys.executable, "-", str(cron), old, new, worker],
                        input=preflight, text=True, capture_output=True, timeout=5)
                    self.assertEqual(outcome.returncode == 0, allowed, outcome.stderr)
                    self.assertIn(message, outcome.stdout + outcome.stderr)


if __name__ == "__main__":
    unittest.main()
