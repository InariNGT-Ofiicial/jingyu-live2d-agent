import unittest
from unittest.mock import Mock,patch
from vts_deploy import load_model
class LoadRetryTests(unittest.TestCase):
 def test_retries_only_cooldown(self):
  v=Mock();v.call.side_effect=[RuntimeError('VTS API error 153: cooldown'),{'modelID':'test'}]
  with patch('vts_deploy.time.sleep'):self.assertEqual(load_model(v,'test'),{'modelID':'test'})
  self.assertEqual(v.call.call_count,2)
 def test_other_api_errors_not_retried(self):
  v=Mock();v.call.side_effect=RuntimeError('VTS API error 999: test')
  with self.assertRaises(RuntimeError):load_model(v,'test')
  self.assertEqual(v.call.call_count,1)
 def test_cooldown_deadline_is_bounded(self):
  v=Mock();v.call.side_effect=RuntimeError('VTS API error 153: cooldown')
  with patch('vts_deploy.time.monotonic',side_effect=[0,21]),self.assertRaises(RuntimeError):load_model(v,'test')
if __name__=='__main__':unittest.main()
