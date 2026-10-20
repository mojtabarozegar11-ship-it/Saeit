import importlib.util
from pathlib import Path
import tempfile,unittest
BASE=Path(__file__).resolve().parents[1]/'scripts'
def load(name):
 spec=importlib.util.spec_from_file_location(name,str(BASE/(name+'.py')))
 mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
maker=load('factory_build50_three_media')
proto=load('factory_build_50')
review=load('factory_three_independent_review')
class ThreeActualNativeBuilders(unittest.TestCase):
 def test_every_family_has_distinct_48_tasks_and_valid_build50_contract(self):
  self.assertEqual(set(maker.PRODUCTS),{'F14','F37','F39'})
  for fid in maker.PRODUCTS:
   p=maker.task_plan(proto,fid)
   self.assertEqual(len(proto.validate_plan(p)),48)
   self.assertNotEqual(p['producer_id'],'human_reviewer')
 def test_html5_gameplay_controls_and_variants(self):
  plan=maker.task_plan(proto,'F14')
  a=maker.game(plan['work_packages'][0])
  b=maker.game(plan['work_packages'][1])
  self.assertNotEqual(a,b)
  for term in ('requestAnimationFrame','function reset','health--','keydown','pointermove'):
   self.assertIn(term,a)
 def test_corrupt_video_is_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'broken.mp4';p.write_bytes(b'X'*2000)
   with self.assertRaisesRegex(ValueError,'MP4_HEADER'):review.validate(p)
if __name__=='__main__':unittest.main()
