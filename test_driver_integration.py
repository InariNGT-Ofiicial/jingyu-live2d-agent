import unittest
from unittest.mock import patch
from compiler import compile_plan,CompileError,EXPRESSIONS,PHYSICS_OUTPUTS
from model_profile import PRIMARY
from vts_adapter import export_calibration,inverse

class DriverIntegrationTests(unittest.TestCase):
    def test_explicit_overlay_and_ownership(self):
        base={'kind':'pose','duration':3,'values':{'LeanInput':-8}}
        expr={'kind':'expression','name':'前倾','duration':3,'strength':.2,'layer':'overlay'}
        for actions in [[base,expr],[expr,base]]:
            c=compile_plan({'version':1,'actions':actions})
            e=next(t for t in c['tracks'] if 'expression' in t)
            self.assertEqual(e['stage'],'expression');self.assertEqual(e['expression']['value'],-30)
            self.assertEqual(e['expression']['weightPoints'][1][1],.2)
        with self.assertRaises(CompileError):compile_plan({'version':1,'actions':[base,{**expr,'layer':'exclusive'}]})
        with self.assertRaises(CompileError):compile_plan({'version':1,'actions':[base,expr,expr]})
        self.assertFalse(set(PRIMARY)&PHYSICS_OUTPUTS)
        with self.assertRaises(CompileError):compile_plan({'version':1,'actions':[{'kind':'pose','values':{'ParamBrowLAngle':.5}}]})
        with self.assertRaises(CompileError):compile_plan({'version':1,'actions':[{'kind':'pose','values':{'ParamBrowLAngleSmoothing':.5}}]})
        compile_plan({'version':1,'actions':[{'kind':'pose','values':{'ParamBrowLY':.5,'ParamMouthForm':.5}}]})

    def test_gesture_overlay_is_rejected(self):
        p={'kind':'expression','name':'竖食指开','duration':5,'layer':'overlay'}
        with self.assertRaises(CompileError):compile_plan({'version':1,'actions':[{'kind':'gesture','name':'point','duration':5},p]})

    def test_multiply_keeps_factor_not_default_value(self):
        with patch.dict(EXPRESSIONS,{'test':{'Parameters':[{'Id':'ParamMouthForm','Value':.5,'Blend':'Multiply'}]}}):
            c=compile_plan({'version':1,'actions':[{'kind':'pose','values':{'ParamMouthForm':.8}},
                {'kind':'expression','name':'test','layer':'overlay','strength':.5}]})
            self.assertEqual(c['tracks'][1]['expression']['value'],.5)

    def test_vts_coupling_and_protocol(self):
        p={'version':1,'actions':[{'kind':'pose','duration':2,'values':{'AngleX':20,'PositionX':20}}]}
        r=export_calibration(p,10);self.assertTrue(r['representable']);self.assertEqual(len(r['frames']),28)
        frame=r['frames'][10]['request'];self.assertEqual(frame['messageType'],'InjectParameterDataRequest')
        self.assertEqual(frame['data']['parameterValues'],[{'id':'FaceAngleX','value':20,'weight':1}])
        p['actions'][0]['values']['PositionX']=5;r=export_calibration(p)
        self.assertFalse(r['representable']);self.assertFalse(r['frames']);self.assertIn('incompatible',r['blockers'][0]['reason'])
        self.assertFalse(export_calibration({'version':1,'actions':[{'kind':'gesture','name':'point','duration':5}]})['representable'])
        self.assertFalse(export_calibration({'version':1,'actions':[{'kind':'pose','values':{'AngleX':20}}]})['representable'])
        self.assertEqual(inverse({'OutputRangeLower':1,'OutputRangeUpper':-1,'InputRangeLower':-.6,'InputRangeUpper':.6},1),-.6)

if __name__=='__main__':unittest.main()
