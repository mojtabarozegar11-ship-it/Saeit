import importlib.util,sys,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]/"scripts"
sys.path.insert(0,str(HERE))
def get(name):
 sp=importlib.util.spec_from_file_location(name,str(HERE/(name+".py")))
 m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
maker=get("factory_build50_five_publications")
protocol=get("factory_build_50")
review=get("factory_five_publication_review")
class FiveLegitimatePilots(unittest.TestCase):
 def test_forty_eight_distinct_native_tasks_per_family(self):
  for fid in maker.PRODUCTS:
   self.assertEqual(len(protocol.validate_plan(maker.plan(protocol,fid))),48)
 def test_every_real_native_format_example_including_epub_stored_first(self):
  try:import reportlab,docx,openpyxl
  except ImportError:self.skipTest("pinned VENV-only imports")
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp)
   for fid in maker.PRODUCTS:
    task=maker.plan(protocol,fid)["work_packages"][0]
    files=maker.make(folder,fid,task)
    self.assertEqual(len(files),len(maker.SCHEMES[fid]))
    self.assertEqual(review.verify_one(folder,task["id"],fid),len(files))
 def test_synthetic_research_and_market_cannot_be_claimed_real(self):
  for fid in ("F04","F05"):
   _,paras=maker.content(fid,{"topic":"storage","variant":"foundation"})
   self.assertIn("synthetic"," ".join(paras).lower())
 def test_mutated_xlsx_provenance_cannot_pass(self):
  try:import reportlab,openpyxl
  except ImportError:self.skipTest("pinned VENV-only imports")
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp);task=maker.plan(protocol,"F05")["work_packages"][0]
   maker.make(folder,"F05",task)
   p=folder/(task["id"]+".xlsx")
   wb=openpyxl.load_workbook(str(p));wb.active["E2"]="REAL SOURCE";wb.save(str(p))
   with self.assertRaisesRegex(ValueError,"XLSX_FALSE_MARKET_DATA"):
    review.verify_one(folder,task["id"],"F05")
if __name__=="__main__":unittest.main()
