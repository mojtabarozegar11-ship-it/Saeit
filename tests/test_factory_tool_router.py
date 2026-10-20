"""Router proves usable entry points, 3000 tools, real family calls and fail-closed safety."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
BASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("tool_router",str(BASE/"scripts/factory_tool_router.py"))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def setup(root):
    reg=BASE/"factory_config/forty_families.json";ops=root/"ops";ops.mkdir()
    (ops/"production-workbench-3000").mkdir()
    a=ops/"production-workbench-3000"
    shutil.copy(BASE/"scripts/factory_3000_workbench.py",a/"runner.py")
    shutil.copy(BASE/"scripts/factory_1000_workbench.py",a/"factory_1000_workbench.py")
    private=root/"private";private.mkdir();toolkit=private/"production-toolkit-3000";toolkit.mkdir()
    wb=m.load(a/"runner.py");cat=wb.catalog(json.loads(reg.read_text()))
    catalog=toolkit/"catalog.json";catalog.write_bytes(m.json_bytes(cat)+b"\n")
    (toolkit/"verification.json").write_text(json.dumps({"schema":"saeit.factory.workbench-verification.v2",
        "synthetic_test_invocations_passed":3000,"new_bindings_added":2000,
        "runtime_sha256":m.digest((a/"runner.py").read_bytes()),
        "base_runtime_sha256":m.digest((a/"factory_1000_workbench.py").read_bytes()),
        "catalog_sha256":m.digest(catalog.read_bytes())}))
    return ops,private,reg
class RouterTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name);self.ops,self.private,self.reg=setup(self.root)
    def test_all_3000_can_route_and_40_real_families_are_consumers(self):
        self.assertEqual(m.selftest(self.ops,self.private,self.reg)["routed"],3000)
        report=m.tick(self.ops,self.private,self.reg)
        self.assertEqual(report["families_connected"],40)
        self.assertEqual(report["support_invocations_this_tick"],400)
        self.assertEqual(len(report["family_readbacks"]),40)
        self.assertEqual(len({y["tool_id"] for row in report["family_readbacks"] for y in row["receipts"]}),400)
        self.assertFalse(report["commercial_release"])
        self.assertEqual(report["agent_workers_confirmed_online"],0)
        self.assertTrue((self.private/"tool-router/dashboard.json").exists())
    def test_direct_worker_and_deferred_queue_use_real_code(self):
        area=m.private_dir(self.private/"tool-router/jobs")
        (area/"in.json").write_text('{"numbers":[3,5,7]}')
        response=m.direct(self.ops,self.private,self.reg,"planner","F27-T26","in.json","out.json")
        self.assertEqual(response["result"]["sum"],15)
        self.assertEqual((area/"out.json").stat().st_mode & 0o777,0o600)
        inbox=m.private_dir(self.private/"tool-router/requests")
        queued={"schema":m.REQUEST_SCHEMA,"request_id":"job001","role":"quality","tool_id":"F01-T60","payload":{"object":{"done":True}}}
        (inbox/"job001.json").write_text(json.dumps(queued))
        report=m.tick(self.ops,self.private,self.reg)
        self.assertEqual(report["queued_requests"]["completed"],1)
        self.assertTrue((self.private/"tool-router/results/job001.json").exists())
        self.assertFalse((inbox/"job001.json").exists())
    def test_rejects_tamper_invalid_roles_paths_and_fake_tools(self):
        with self.assertRaises(ValueError):
            m.direct(self.ops,self.private,self.reg,"rogue","F01-T26","a.json","b.json")
        with self.assertRaises(ValueError):
            m.direct(self.ops,self.private,self.reg,"planner","F01-T26","../a.json","b.json")
        wb,cat,_,_,_=m.verified(self.ops,self.private,self.reg)
        with self.assertRaises(ValueError):m.execute(wb,cat,"F41-T26",{"numbers":[1]})
        area=self.private/"production-toolkit-3000/catalog.json"
        area.write_text('{"fake":true}')
        with self.assertRaises(ValueError):m.verified(self.ops,self.private,self.reg)
if __name__=="__main__":unittest.main()
