import json,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
from planner import Planner,PlannerError,output_text
import server
from compiler import compile_plan
PLAN={'version':1,'actions':[{'kind':'nod','at':0,'duration':2,'strength':.5}]}

class BetaTests(unittest.TestCase):
 def test_persist_settings_without_key(self):
  base=Path(__file__).resolve().parent/'.local/tests';base.mkdir(parents=True,exist_ok=True)
  with tempfile.TemporaryDirectory(dir=base) as d:
   self.assertIn(base.resolve(),Path(d).resolve().parents)
   file=Path(d)/'config.json';p=Planner(file);p.configure({'provider':'openai','model':'test-model','apiKey':'not-a-real-key'})
   self.assertNotIn('not-a-real-key',file.read_text());self.assertNotIn('apiKey',json.loads(file.read_text()))
   with patch.dict('os.environ',{'OPENAI_API_KEY':'','L2D_LLM_API_KEY':''}):q=Planner(file)
   self.assertEqual(q.public()['model'],'test-model');self.assertFalse(q.public()['hasApiKey'])
 def test_changed_endpoint_drops_old_key(self):
  p=Planner();p.configure({'provider':'openai','model':'test','apiKey':'not-a-real-key'});p.configure({'baseUrl':'https://example.test/v1'})
  self.assertFalse(p.public()['hasApiKey'])
 def test_non_object_provider_response(self):
  for protocol in ['responses','chat_completions']:
   for obj in [[],None,'bad']:
    with self.assertRaises(PlannerError):output_text(obj,protocol)
 def test_backend_bound_at_generation(self):
  server.PLANS.clear();server.BACKEND='web'
  with patch.object(server.PLANNER,'public',return_value={'ready':True}),patch.object(server.PLANNER,'plan',return_value={'plan':PLAN,'compiled':compile_plan(PLAN),'planner':{'model':'mock'}}):
   task=server.start_planning('点头','vts');server.BACKEND='web'
   for _ in range(100):
    t=next(t for t in server.PLANS if t['id']==task['id'])
    if not t['running']:break
    time.sleep(.01)
   self.assertEqual(t['backend'],'vts');self.assertEqual(t['status'],'validated')
 def test_cancel_does_not_accept_late_result(self):
  server.PLANS.clear();gate=threading.Event()
  def blocked(prompt,update):
   gate.wait(2);update('repairing');return {'plan':PLAN,'compiled':compile_plan(PLAN),'planner':{'model':'mock'}}
  with patch.object(server.PLANNER,'public',return_value={'ready':True}),patch.object(server.PLANNER,'plan',side_effect=blocked):
   task=server.start_planning('点头','web');t=next(x for x in server.PLANS if x['id']==task['id'])
   with server.LOCK:t['status']='cancelled'
   with self.assertRaises(PlannerError):server.start_planning('第二个请求','web')
   gate.set()
   for _ in range(100):
    if not t['running']:break
    time.sleep(.01)
   self.assertEqual(t['status'],'cancelled');self.assertNotIn('plan',t)

if __name__=='__main__':unittest.main()
