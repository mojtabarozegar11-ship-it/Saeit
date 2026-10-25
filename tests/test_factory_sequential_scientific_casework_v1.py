"""Real per-product queue rotation; no invented science, QA or store release."""
import fcntl
import importlib.util
import json
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
            self.assertEqual(first["decision"],"RETURN_TO_PRODUCTION")
            self.assertRegex(first["source_order_sha256"], r"^[a-f0-9]{64}$")
            self.assertRegex(first["receipt_sha256"], r"^[a-f0-9]{64}$")
            self.assertGreaterEqual(first["elapsed_ms"], 0)
            target=root/"production-instructions/stage-02/primary-source-acquisition-v1"
            receipt_path=root/"production-instructions"/first["receipt_relative_path"]
            self.assertTrue(receipt_path.is_file())
            import hashlib
            self.assertEqual(hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
                             first["receipt_sha256"])
            self.assertEqual(json.loads(receipt_path.read_text())["independent_qc_stage"],
                             "NOT_PERFORMED")
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

    def test_queue_insertion_before_cursor_does_not_repeat_old_product(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            fixture(root,3)
            first=step_with_ample_disk(root,max_attempts=0)
            self.assertEqual(first["selected_order_file"],"WO-00000001--r001.json")
            inbox=root/"production-instructions/stage-02/primary-fulltext-repair-inbox"
            new_name="WO-00000000--r001.json"
            packet=json.loads((inbox/"WO-00000001--r001.json").read_text())
            packet["order_file"]=new_name
            (inbox/new_name).write_text(json.dumps(packet))
            second=step_with_ample_disk(root,max_attempts=0)
            self.assertEqual(second["selected_order_file"],"WO-00000002--r001.json")

    def test_queue_removal_before_cursor_does_not_repeat_product(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            fixture(root,3)
            step_with_ample_disk(root,max_attempts=0)
            second=step_with_ample_disk(root,max_attempts=0)
            self.assertEqual(second["selected_order_file"],"WO-00000002--r001.json")
            inbox=root/"production-instructions/stage-02/primary-fulltext-repair-inbox"
            (inbox/"WO-00000001--r001.json").unlink()
            third=step_with_ample_disk(root,max_attempts=0)
            self.assertEqual(third["selected_order_file"],"WO-00000003--r001.json")

    def test_malicious_cursor_identity_fails_closed_without_product_work(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            fixture(root,2)
            target=root/"production-instructions/stage-02/primary-source-acquisition-v1"
            target.mkdir()
            (target/".product-sequential-cursor.json").write_text(json.dumps({
                "schema":worker.SCHEMA,"next_index":1,"last_order_file":"../secret"}))
            with self.assertRaisesRegex(ValueError,"CASEWORK_CURSOR_LAST_ORDER_INVALID"):
                worker.step(root,dry_run=True)

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


if __name__ == "__main__":
    unittest.main()
