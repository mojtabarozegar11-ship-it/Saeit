import importlib.util
from pathlib import Path
import tempfile,unittest
BASE=Path(__file__).resolve().parents[1]/'scripts'
def load(n):
 sp=importlib.util.spec_from_file_location(n,str(BASE/(n+'.py')))
 m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
maker=load('factory_build50_next4_media')
proto=load('factory_build_50')
review=load('factory_next4_review')
class RealNext4(unittest.TestCase):
 def test_every_family_has_48_new_different_task_contracts(self):
  self.assertEqual(len(maker.PRODUCTS),4)
  for family in maker.PRODUCTS:
   plan=maker.plan(proto,family)
   self.assertEqual(len(proto.validate_plan(plan)),48)
 def test_corrupt_multimedia_cannot_pass(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'fake.mp4';p.write_bytes(b'A'*2000)
   with self.assertRaisesRegex(ValueError,'UNPLAYABLE_VIDEO'):review.validate(p)
 def test_subtitle_is_real_timed_text(self):
  with tempfile.TemporaryDirectory() as tmp:
   task=maker.plan(proto,'F08')['work_packages'][0]
   name=maker.subtitle(Path(tmp),task)
   self.assertTrue((Path(tmp)/name).read_text().startswith('WEBVTT'))
if __name__=='__main__':unittest.main()
