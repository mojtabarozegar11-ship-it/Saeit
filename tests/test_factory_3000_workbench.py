"""Verify 2,000 new functional bindings plus preservation of the original 1,000."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("factory_3000",ROOT/"scripts/factory_3000_workbench.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def registry():
    return {"schema":"saeit.factory.family-registry.v1","profiles":[{"id":"F%02d"%n,"slug":"family_%02d"%n} for n in range(1,41)]}
class Workbench3000(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.cat=m.catalog(registry())
    def test_all_3000_work(self):
        result=m.selftest(self.cat)
        self.assertEqual(result["passed"],3000)
        self.assertEqual(result["new_bindings"],2000)
        self.assertEqual(len(set(x["id"] for x in self.cat["tools"])),3000)
        self.assertEqual(self.cat["native_manufacturing_executors_added"],0)
    def test_50_new_tools_per_family(self):
        for n in range(1,41):
            ops=[x["operation"] for x in self.cat["tools"] if x["family_id"]=="F%02d"%n]
            self.assertEqual(ops,list(range(1,76)))
            self.assertTrue(all(x["commercial_publication_allowed"] is False for x in self.cat["tools"]))
    def test_real_utility_results(self):
        self.assertEqual(m.dispatch(26,{"numbers":[2,3]})["sum"],5)
        self.assertEqual(m.dispatch(28,{"numbers":[1,2,3]})["median"],2)
        self.assertEqual(m.dispatch(37,{"text":"café"})["text"],"cafe")
        self.assertEqual(m.dispatch(46,{"csv":"k,v\na,1\na,2\n","column":"k"})["groups"]["a"],2)
        self.assertEqual(m.dispatch(47,{"csv":"k,v\na,1\na,2\n","column":"k","value_column":"v"})["sums"]["a"],3)
        self.assertEqual(m.dispatch(56,{"object":{"a":7},"pointer":"/a"})["value"],7)
        self.assertEqual(len(m.dispatch(57,{"items":[1,1,2]})["items"]),2)
        self.assertEqual(m.dispatch(61,{"object":{"token":"abc"}})["redacted"]["token"],"***REDACTED***")
        self.assertIn("q=a+b",m.dispatch(66,{"url":"https://example.org","params":{"q":"a b"}})["url"])
        self.assertIn("&lt;",m.dispatch(72,{"text":"<img>"})["html"])
        self.assertEqual(m.dispatch(74,{"nodes":["b","a"],"edges":[["a","b"]]})["order"],["a","b"])
        self.assertFalse(m.dispatch(75,{"assets":[{"path":"x","text":"x","expected_sha256":"0"*64}]})["all_match"])
    def test_reject_unsafe(self):
        for op,p in ((26,{"numbers":[float("nan")]}),(32,{"numbers":[1],"window":3}),
          (54,{"csv":"a,b\n1,2\n","right_csv":"c,d\n1,2\n"}),(66,{"url":"file:///etc/passwd"}),
          (74,{"nodes":["a","b"],"edges":[["a","b"],["b","a"]]})):
            with self.subTest(op=op):
                with self.assertRaises(ValueError):m.dispatch(op,p)
        with self.assertRaises(ValueError):m.invoke(self.cat,"F41-T75",{})
    def test_cli_private_actual_io(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/"registry.json").write_text(json.dumps(registry()))
            m.main(["--registry",str(p/"registry.json"),"--catalog-out",str(p/"catalog.json"),"--selftest"])
            self.assertEqual(json.loads((p/"catalog.json").read_text())["tools_count"],3000)
            (p/"in.json").write_text(json.dumps({"numbers":[4,5,6]}))
            m.main(["--registry",str(p/"registry.json"),"--tool-id","F40-T26","--workspace",d,"--input-file",str(p/"in.json"),"--output-file",str(p/"out.json")])
            self.assertEqual(json.loads((p/"out.json").read_text())["result"]["sum"],15)
            self.assertEqual((p/"out.json").stat().st_mode & 0o777,0o600)
if __name__=="__main__":unittest.main()
