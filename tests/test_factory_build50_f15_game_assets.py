import importlib.util
from pathlib import Path
import tempfile,unittest
BASE=Path(__file__).resolve().parents[1]/'scripts'
def load(name):
 sp=importlib.util.spec_from_file_location(name,str(BASE/(name+'.py')))
 m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
maker=load('factory_build50_f15_game_assets')
proto=load('factory_build_50')
review=load('factory_f15_independent_review')
class NativeGameAssetProof(unittest.TestCase):
 def test_contract_enforces_48_distinct_native_tasks(self):
  tasks=proto.validate_plan(maker.plan(proto))
  self.assertEqual(len(tasks),48)
  self.assertEqual(len({t['id'] for t in tasks}),48)
 def test_real_glb_has_valid_vertices_indices_and_binary_buffers(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'item.glb'
   task=maker.plan(proto)['work_packages'][0]
   maker.make_glb(path,task,0,0)
   review.check_file(path)
   self.assertEqual(path.read_bytes()[:4],b'glTF')
 def test_forged_glb_or_audio_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'fake.glb';path.write_bytes(b'Z'*256)
   with self.assertRaisesRegex(ValueError,'NOT_GLB'):review.check_file(path)
if __name__=='__main__':unittest.main()
