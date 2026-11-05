import unittest
from copy import deepcopy
from arm_binding import bind_arm_tracks,sample

class ArmBindingTests(unittest.TestCase):
    def fixture(self,forearm):
        joints={k:k for k in ['upperArm','forearm','wrist','perspective']}
        rest={'upperArm':0,'forearm':forearm,'wrist':0,'perspective':.2}
        limits={k:{'min':-1,'max':1} for k in joints}
        tracks=[{'id':k,'points':[[0,0],[1,v],[2,v],[3, -.6 if k=='forearm' else .3 if k=='upperArm' else v],[4,v],[5,v],[6,0]]} for k,v in rest.items()]
        return tracks,joints,rest,limits
    def test_author_entry_exit_preserved_and_bounded(self):
        tracks,joints,rest,limits=self.fixture(.7);old=deepcopy(tracks)
        self.assertTrue(bind_arm_tracks(tracks,joints,rest,1,5,limits))
        for tr,orig in zip(tracks,old):
            for t in [0,.5,1,5,5.5,6]:self.assertAlmostEqual(sample(tr['points'],t),sample(orig['points'],t),places=5)
            self.assertTrue(all(-1<=v<=1 for _,v in tr['points']))
        self.assertGreater(sample(tracks[1]['points'],3),.4)
    def test_gesture_anchor_not_universal_angle(self):
        a,j,r,l=self.fixture(.7);b,j2,r2,l2=self.fixture(-.73)
        bind_arm_tracks(a,j,r,1,5,l);bind_arm_tracks(b,j2,r2,1,5,l2)
        self.assertGreater(sample(a[1]['points'],3),0)
        self.assertLess(sample(b[1]['points'],3),0)
    def test_upper_arm_moves_forearm_and_rest_is_unchanged(self):
        tracks,joints,rest,limits=self.fixture(.7)
        tracks[1]['points']=[[0,0],[1,.7],[5,.7],[6,0]]
        bind_arm_tracks(tracks,joints,rest,1,5,limits)
        self.assertGreater(sample(tracks[1]['points'],3),.7)
        self.assertAlmostEqual(sample(tracks[1]['points'],2),.7,places=5)
