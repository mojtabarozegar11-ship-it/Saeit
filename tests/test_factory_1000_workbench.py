"""All 1000 factory support tools must execute, not merely appear in a menu."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

FILE=Path(__file__).resolve().parents[1]/"scripts/factory_1000_workbench.py"
spec=importlib.util.spec_from_file_location("factory_1000_workbench", FILE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def registry():
    return {"schema":"saeit.factory.family-registry.v1",
            "profiles":[{"id":"F%02d"%i,"slug":"factory_family_%02d"%i} for i in range(1,41)]}

class ThousandOperationalTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog=m.catalog(registry())

    def test_all_1000_unique_callable_tools_have_measured_qa(self):
        actual=m.selftest(self.catalog)
        self.assertEqual(actual["tested"],1000)
        self.assertEqual(actual["passed"],1000)
        self.assertEqual(actual["failed"],0)
        self.assertEqual(len({z["id"] for z in self.catalog["tools"]}),1000)
        self.assertEqual(self.catalog["native_manufacturing_executors_added"],0)
        self.assertEqual(self.catalog["commercially_approved_products_added"],0)

    def test_every_family_has_25_independent_registered_commands(self):
        for i in range(1,41):
            tid="F%02d"%i
            tools=[x for x in self.catalog["tools"] if x["family_id"]==tid]
            self.assertEqual([x["operation"] for x in tools],list(range(1,26)))
            self.assertEqual(len(set(x["id"] for x in tools)),25)
            for tool in tools:
                self.assertFalse(tool["commercial_publication_allowed"])

    def test_calculation_correctness_of_core_utilities(self):
        self.assertEqual(m.dispatch(1,{"text":"  a  \n  b  "})["normalized"],"a b")
        self.assertEqual(m.dispatch(2,{"text":"# H\n## section"})["headings"][1]["level"],2)
        self.assertEqual(m.dispatch(3,{"text":"one two two"})["words"],3)
        self.assertEqual(m.dispatch(4,{"text":"one two two"})["frequencies"][0],{"word":"two","count":2})
        self.assertEqual(len(m.dispatch(5,{"text":"- [x] done\n- [ ] todo"})["checklist"]),2)
        self.assertEqual(m.dispatch(7,{"csv":"a,b\n1,2\n1,2\n"})["removed"],1)
        self.assertEqual(m.dispatch(9,{"csv":"a,b\n1,2\n3,4\n","column":"a","value":"3"})["matched"],1)
        self.assertEqual(len(m.dispatch(10,{"csv":"a,b\n1,2\n"})["rows"]),1)
        self.assertEqual(m.dispatch(12,{"object":{"a":{"b":7}}})["flat"]["a.b"],7)
        self.assertEqual(m.dispatch(13,{"before":{"a":1},"after":{"a":2}})["changed"],["a"])
        self.assertEqual(m.dispatch(14,{"object":{"a":1},"required":["a","b"]})["missing"],["b"])
        self.assertEqual(m.dispatch(15,{"base":{"x":1},"patch":{"x":2}})["merged"]["x"],2)
        self.assertEqual(m.dispatch(16,{"text":"abc"})["sha256"],"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        self.assertTrue(m.dispatch(17,{"assets":[{"path":"a.txt","text":"abc"}]})["assets"][0]["sha256"])
        self.assertFalse(m.dispatch(18,{"assets":[{"path":"a.svg","third_party":True}]})["documentation_complete"])
        self.assertFalse(m.dispatch(19,{"paths":["../escape.txt"]})["all_safe"])
        self.assertIn("&lt;tag&gt;",m.dispatch(20,{"title":"Title <tag>","description":"Description with & text and content"})["html"])
        self.assertEqual(m.dispatch(21,{"text":"Sample Product Here"})["slug"],"sample-product-here")
        self.assertEqual(m.dispatch(23,{"risks":[{"name":"risk","likelihood":3,"impact":4}]})["ranked"][0]["score"],12)
        self.assertFalse(m.dispatch(24,{"checks":[{"id":"A","passed":True,"evidence_sha256":"f"*64}]})["commercial_release_authorized"])
        self.assertEqual(len(m.dispatch(25,{"deliverables":["A","B"]})["work_items"]),14)

    def test_security_constraints_are_enforced(self):
        for name in ("../escape","/etc/passwd","x\\windows","bad//name","C:/secret"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):m.safe_name(name)
        with self.assertRaises(ValueError):
            m.invoke(self.catalog,"F41-T01",{"text":"example"})
        with self.assertRaises(ValueError):
            m.invoke(self.catalog,"F01-T01",{"text":"a"*220000})
        with self.assertRaises(ValueError):
            m.dispatch(11,{"rows":[{"nested":{"unsafe":3}}]})
        with self.assertRaises(ValueError):
            m.dispatch(23,{"risks":[{"name":"bad","likelihood":True,"impact":3}]})
        with self.assertRaises(ValueError):
            m.dispatch(22,{"requirements":[{"id":"a"},{"id":"a"}]})

    def test_real_private_command_line_generates_1000_item_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            reg=folder/"registry.json";out=folder/"catalog.json"
            reg.write_text(json.dumps(registry()),encoding="utf8")
            self.assertEqual(m.main(["--registry",str(reg),"--catalog-out",str(out),"--selftest"]),0)
            cat=json.loads(out.read_text(encoding="utf8"))
            self.assertEqual(cat["tools_count"],1000)
            self.assertEqual(out.stat().st_mode & 0o777,0o600)
            incoming=folder/"request.json";response=folder/"result.json"
            incoming.write_text(json.dumps({"text":" A  B "}),encoding="utf8")
            m.main(["--registry",str(reg),"--tool-id","F40-T01","--workspace",str(folder),"--input-file",str(incoming),"--output-file",str(response)])
            data=json.loads(response.read_text(encoding="utf8"))
            self.assertEqual(data["result"]["normalized"],"A B")
            self.assertTrue(data["noncommercial"])
            self.assertEqual(response.stat().st_mode & 0o777,0o600)
            with self.assertRaisesRegex(ValueError,"WORKBENCH_PATH_OUTSIDE_PRIVATE_WORKSPACE"):
                m.main(["--registry",str(reg),"--tool-id","F40-T01",
                    "--workspace",str(folder),"--input-file","/etc/passwd",
                    "--output-file",str(response)])

if __name__=="__main__":
    unittest.main()
