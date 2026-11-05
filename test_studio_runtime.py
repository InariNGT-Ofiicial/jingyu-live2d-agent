import unittest
from unittest.mock import patch
from studio_runtime import Studio

class StudioTests(unittest.TestCase):
 def setUp(self):
  self.events=[];self.s=Studio(lambda k,v:self.events.append((k,v)))
  self.s.heartbeat({'clientId':'page','ready':True})
 def test_no_ambiguous_playback(self):
  self.s.heartbeat({'clientId':'other','ready':True})
  with self.assertRaises(ValueError):self.s.command({'action':'play'})
  self.assertEqual(self.s.command({'action':'play','clientId':'page'})['clientId'],'page')
 def test_receipt_owner_and_terminal(self):
  j=self.s.command({'action':'play','clientId':'page'})
  self.s.heartbeat({'clientId':'other','ready':True})
  with self.assertRaises(ValueError):self.s.report({'clientId':'other','jobId':j['id'],'status':'completed'})
  self.s.report({'clientId':'page','jobId':j['id'],'status':'interrupted'})
  self.s.report({'clientId':'page','jobId':j['id'],'status':'playing'})
  self.assertEqual(self.s.state()['jobs'][0]['status'],'interrupted')
 def test_invalid_scene_has_no_partial_changes(self):
  before=self.s.state()['scene']
  with self.assertRaises(ValueError):self.s.command({'action':'set','scene':{'theme':'cool','camera':'orbit'}})
  self.assertEqual(before,self.s.state()['scene'])
 def test_disconnect_marks_unfinished_job(self):
  self.s.command({'action':'play','clientId':'page'})
  with patch('studio_runtime.time.monotonic',return_value=10**20):
   state=self.s.state()
  self.assertFalse(state['clients']);self.assertEqual(state['jobs'][0]['status'],'error')
 def test_live_speech_requires_stream_and_uses_receipts(self):
  with self.assertRaises(ValueError):self.s.command({'action':'speak','clientId':'page'})
  job=self.s.command({'action':'speak','clientId':'page','speech':{'id':'voice','streamUrl':'/stream'}})
  self.assertEqual(job['status'],'accepted')
  self.s.report({'clientId':'page','jobId':job['id'],'status':'preparing'})
  self.assertEqual(self.s.state()['jobs'][0]['status'],'preparing')
  self.s.report({'clientId':'page','jobId':job['id'],'status':'playing'})
  self.assertEqual(self.s.state()['jobs'][0]['status'],'playing')
  self.s.report({'clientId':'page','jobId':job['id'],'status':'completed'})
  self.assertEqual(self.s.state()['jobs'][0]['status'],'completed')
if __name__=='__main__':unittest.main()
