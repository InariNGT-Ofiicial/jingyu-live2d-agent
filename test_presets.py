import json,tempfile,unittest
from pathlib import Path
from presets import PresetStore
from compiler import CompileError
PLAN={'version':1,'actions':[{'kind':'nod','at':0,'duration':2,'strength':.5}]}
class PresetTests(unittest.TestCase):
 def setUp(self):
  base=Path(__file__).resolve().parent/'.local/tests';base.mkdir(parents=True,exist_ok=True)
  self.temp=tempfile.TemporaryDirectory(dir=base);self.path=Path(self.temp.name)/'presets.json';self.store=PresetStore(self.path)
 def tearDown(self):self.temp.cleanup()
 def test_roundtrip_restart_and_delete(self):
  p=self.store.save('点头',PLAN);restored=PresetStore(self.path)
  self.assertEqual(restored.get(p['id'])['plan'],PLAN);restored.delete(p['id']);self.assertEqual(PresetStore(self.path).list(),[])
  with self.assertRaises(CompileError):restored.get(p['id'])
 def test_invalid_and_duplicate_do_not_clobber(self):
  p=self.store.save('点头',PLAN)
  for name,plan in [('点头',PLAN),('',PLAN),('错误',{'actions':[{'kind':'fly'}]})]:
   with self.assertRaises(CompileError):self.store.save(name,plan)
  self.assertEqual(self.store.list(),[p])
 def test_corrupt_file_not_overwritten(self):
  self.path.write_text('broken')
  with self.assertRaises(CompileError):self.store.save('点头',PLAN)
  self.assertEqual(self.path.read_text(),'broken')
 def test_id_not_file_path(self):
  p=self.store.save('../只作标题',PLAN)
  with self.assertRaises(CompileError):self.store.delete('../presets.json')
  self.assertEqual(self.store.get(p['id'])['name'],'../只作标题')
if __name__=='__main__':unittest.main()
