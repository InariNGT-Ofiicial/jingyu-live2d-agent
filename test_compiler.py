import unittest
from copy import deepcopy
from compiler import compile_plan, CompileError
from model_profile import PARAMS, GESTURES
from demos import DEMOS

class CompilerTests(unittest.TestCase):
    def test_continuous_trajectory_and_face_inputs(self):
        frames=[{'time':1,'values':{'AngleX':28,'MouthX':-.8}}, {'time':3,'values':{'AngleX':-28,'MouthX':.8}}]
        r=compile_plan({'version':1,'actions':[{'kind':'trajectory','duration':4,'frames':frames}]})
        self.assertEqual(r['tracks'][0]['points'],[[0,0],[1,28],[3,-28],[4,0]])
        for bad in [list(reversed(frames)),[frames[0],{'time':3,'values':{'AngleX':2}}],
                    [{'time':1,'values':{'ParamAngleX':30}},{'time':2,'values':{'ParamAngleX':0}}],
                    [{'time':1,'values':{'AngleX':31}},{'time':2,'values':{'AngleX':0}}]]:
            with self.assertRaises(CompileError):
                compile_plan({'version':1,'actions':[{'kind':'trajectory','duration':4,'frames':bad}]})

    def test_demos_bounded_and_return_neutral(self):
        for plan in DEMOS.values():
            result=compile_plan(plan)
            for tr in result['tracks']:
                p=PARAMS[tr['id']]
                self.assertAlmostEqual(tr['points'][-1][1],p['default'],places=5)
                for time,value in tr['points']:
                    self.assertGreaterEqual(value,p['min'])
                    self.assertLessEqual(value,p['max'])
                    self.assertGreaterEqual(time,0)
                    self.assertLessEqual(time,tr['duration']+.0001)

    def test_overlaps_rejected_but_parallel_channels_allowed(self):
        with self.assertRaises(CompileError):
            compile_plan({'version':1,'actions':[{'kind':'nod'},{'kind':'look','direction':'down'}]})
        compile_plan({'version':1,'actions':[{'kind':'nod'},{'kind':'smile'}]})

    def test_no_direct_physics_output_or_nonfinite(self):
        for values in [{'ParamAngleX':10},{'AngleX':float('nan')},{'AngleX':31},{'AngleX':True}]:
            with self.assertRaises(CompileError):
                compile_plan({'version':1,'actions':[{'kind':'pose','values':values}]})

    def test_native_gestures_keep_exit_and_warn_on_short_duration(self):
        for name in GESTURES:
            result=compile_plan({'version':1,'actions':[{'kind':'gesture','name':name,'duration':.2}]})
            self.assertTrue(result['warnings'])
            self.assertGreater(result['duration'],2)
            self.assertTrue(all(t['points'][-1][1]==PARAMS[t['id']]['default'] for t in result['tracks']))

    def test_unsupported_and_too_long_rejected(self):
        for action in [{'kind':'run'},{'kind':'nod','at':59,'duration':4},{'kind':'blink','duration':.2,'count':4}]:
            with self.assertRaises(CompileError):compile_plan({'version':1,'actions':[action]})

    def test_shake_has_both_sides(self):
        r=compile_plan(DEMOS['no'])
        values=[p[1] for t in r['tracks'] if t['id']=='AngleX' for p in t['points']]
        self.assertLess(min(values),-5)
        self.assertGreater(max(values),5)

    def test_joint_accents_preserve_authored_entry_exit(self):
        for name in GESTURES:
            action={'kind':'gesture','name':name,'duration':10}
            original=compile_plan({'version':1,'actions':[action]})
            action['accents']=[{'at':2,'duration':3,'values':{'wrist':.5}}]
            edited=compile_plan({'version':1,'actions':[action]})
            for old,new in zip(original['tracks'],edited['tracks']):
                self.assertEqual([p for p in old['points'] if p[0]<2 or p[0]>5],
                                 [p for p in new['points'] if p[0]<2 or p[0]>5])
                self.assertEqual(new['points'][-1][1],PARAMS[new['id']]['default'])
            self.assertTrue(any([2.5,.5] in t['points'] for t in edited['tracks']))

    def test_joint_accents_reject_wrong_context_and_invalid_timing(self):
        for accents in [None,[{'at':0,'duration':2,'values':{'wrist':.5}}],
            [{'at':8,'duration':2,'values':{'wrist':.5}}],
            [{'at':2,'duration':2,'values':{'RArm':.5}}],
            [{'at':2,'duration':2,'values':{'wrist':2}}],
            [{'at':2,'duration':2,'values':{'wrist':float('nan')}}],
            [{'at':2,'duration':3,'values':{'wrist':.5}},{'at':4,'duration':2,'values':{'wrist':-.5}}]]:
            with self.assertRaises(CompileError):
                compile_plan({'version':1,'actions':[{'kind':'gesture','name':'point','duration':10,'accents':accents}]})

if __name__=='__main__':unittest.main()
