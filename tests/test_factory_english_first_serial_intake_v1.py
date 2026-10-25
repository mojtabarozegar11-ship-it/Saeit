import importlib.util
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
import subprocess

SCRIPT=Path(__file__).resolve().parents[1]/"scripts/factory_english_first_serial_intake_v1.py"
spec=importlib.util.spec_from_file_location("english_serial",SCRIPT)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class EnglishFirstQueueTests(unittest.TestCase):
    def test_declared_language_groups(self):
        self.assertEqual(m.locale_group({"editions":[{"locale":"en-GB"}]}),0)
        self.assertEqual(m.locale_group({"editions":[{"locale":"fa-IR"},{"locale":"en-US"}]}),1)
        self.assertEqual(m.locale_group({"editions":[{"locale":"fa-IR"}]}),2)
        self.assertEqual(m.locale_group({"editions":[]}),3)
        self.assertEqual(m.locale_group({"instruction":"write English","editions":[]}),3)
        self.assertEqual(m.locale_group({"editions":[{"locale":"de-DE"},{"locale":"en-GB"}]}),1)

    def make_queue(self,temp):
        root=Path(temp)/"private"
        area=root/"production-instructions"
        orders=area/"orders"
        ops=Path(temp)/"ops"
        (area/"stage-06").mkdir(parents=True)
        orders.mkdir()
        ops.mkdir()
        for i in range(1,2001):
            obj={"id":"WO-%08d"%i,"status":"issued","priority":"P0","priority_rank":i}
            if i==1997:
                obj["editions"]=[{"locale":"fa-IR"},{"locale":"en-US"}]
            if i==1998:
                obj["editions"]=[{"locale":"fa-IR"}]
            if i==1999:
                obj["editions"]=[{"locale":"en-GB"}]
            (orders/("%s.json"%obj["id"])).write_text(json.dumps(obj),encoding="utf8")
        return root,ops,area

    def test_priority_is_english_only_then_english_bilingual(self):
        with tempfile.TemporaryDirectory() as d:
            root,ops,area=self.make_queue(d)
            ids,hashsum,counts=m.workorders(area)
            self.assertEqual(len(ids),2000)
            self.assertEqual(ids[0],"WO-00001999")
            self.assertEqual(ids[1],"WO-00001997")
            self.assertEqual(ids[2],"WO-00001998")
            self.assertEqual(counts,{"english_only":1,"english_and_other":1,
                                     "other_language":1,"language_unspecified":1997})
            self.assertEqual(len(hashsum),64)

    def test_dry_run_admits_nothing_and_keeps_order_list(self):
        with tempfile.TemporaryDirectory() as d:
            root,ops,area=self.make_queue(d)
            r=m.run(root,ops,dry_run=True)
            self.assertEqual(r["active_order"],"WO-00001999")
            self.assertEqual(r["orders_preserved"],2000)
            self.assertEqual(r["mode"],"dry_run_no_writes")
            self.assertFalse((area/"stage-06/english-first-active-v1.json").exists())
            self.assertFalse((area/"english-first-ranked-order-list-v1.json").exists())
            self.assertFalse((area/"stage-02").exists())
            self.assertEqual(len(list((area/"orders").iterdir())),2000)

    def test_stale_active_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root,ops,area=self.make_queue(d)
            (area/"stage-06/english-first-active-v1.json").write_text(
                json.dumps({"schema":m.SCHEMA,"index":99,"active_order":"WO-00000099",
                            "queue_sha256":"0"*64}),encoding="utf8")
            with self.assertRaisesRegex(RuntimeError,"STALE_OR_CORRUPT"):
                m.run(root,ops,dry_run=True)

    def test_cron_exclusivity_rejects_bulk_stage1(self):
        fake=subprocess.CompletedProcess(["crontab","-l"],0,
                "* * * * * python3 worker.py # SAEIT_ENGLISH_FIRST_SINGLE_ACTIVE_20261025\n"+
                "* * * * * python3 bulk.py # SAEIT_FACTORY_STAGE1_INDEPENDENT_V1\n","")
        with patch.object(m.subprocess,"run",return_value=fake):
            with self.assertRaisesRegex(RuntimeError,"COMPETING_BULK"):
                m.cron_single()

    def test_id_validator_rejects_injected_file(self):
        with tempfile.TemporaryDirectory() as d:
            root,ops,area=self.make_queue(d)
            (area/"orders"/"untrusted.txt").write_text("x",encoding="utf8")
            with self.assertRaisesRegex(RuntimeError,"BAD_ORDER_FILE"):
                m.workorders(area)


if __name__=="__main__":
    unittest.main()
