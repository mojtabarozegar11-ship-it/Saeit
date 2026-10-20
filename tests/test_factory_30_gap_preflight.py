import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
S=Path(__file__).resolve().parents[1]/"scripts"
def load(name):
    sp=importlib.util.spec_from_file_location(name,str(S/(name+".py")))
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
m=load("factory_30_gap_preflight")
routes=load("factory_product_routes")
class FamilyEngineeringGates(unittest.TestCase):
    def test_all_forty_unique_48_step_acceptance_contracts(self):
        reg=json.loads((S.parent/"factory_config/forty_families.json").read_text())
        all_specs=[m.contract(p,routes) for p in reg["profiles"]]
        self.assertEqual(len(all_specs),40)
        self.assertEqual(len({x["family_id"] for x in all_specs}),40)
        self.assertTrue(all(len(x["work_packages"])==48 for x in all_specs))
        self.assertTrue(all(len({t["id"] for t in x["work_packages"]})==48 for x in all_specs))
        self.assertTrue(all(x["native_maker_installed_by_contract"] is False for x in all_specs))
        self.assertTrue(all(x["completed_work_packages"]==0 for x in all_specs))
    def test_actual_json_svg_zip_signatures_and_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/"content.json").write_text('{"ok":true}',encoding="utf8")
            (root/"icon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path d="M1 1 L8 8"/></svg>')
            with zipfile.ZipFile(root/"report.docx","w") as z:z.writestr("word/document.xml","<w:document/>")
            for name,fmt in (("content.json","JSON"),("icon.svg","SVG"),("report.docx","DOCX")):
                measured=m.validate_file(root/name,fmt)
                self.assertTrue(measured["structurally_parseable"])
                path=root/"manifest.json"
                path.write_text(json.dumps({"family_id":"F01","outputs":[{"path":name,"format":fmt,"sha256":measured["sha256"]}]}))
                self.assertEqual(m.validate_manifest("F01",path,root)["checked"],1)
            (root/"manifest.json").write_text(json.dumps({"family_id":"F01","outputs":[{"path":"content.json","format":"JSON","sha256":"0"*64}]}))
            with self.assertRaisesRegex(ValueError,"HASH_MISMATCH"):
                m.validate_manifest("F01",root/"manifest.json",root)
    def test_no_forged_native_outputs_and_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/"fake.mp4").write_bytes(b"this is not video")
            with self.assertRaisesRegex(ValueError,"MP4_HEADER"):m.validate_file(p/"fake.mp4","MP4")
            (p/"fake.json").write_text("{}")
            doc={"family_id":"F01","outputs":[{"path":"../fake.json","format":"JSON","sha256":"0"*64}]}
            (p/"m.json").write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError,"MANIFEST_PATH"):m.validate_manifest("F01",p/"m.json",p)
if __name__=="__main__":unittest.main()
