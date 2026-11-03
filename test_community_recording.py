import unittest
from compiler import CompileError, compile_plan

def recorded(frames):
    return compile_plan({'version':1,'actions':[{'kind':'recorded','duration':1,'frames':frames}]})

class CommunityRecordingTests(unittest.TestCase):
    def test_sparse_frames_restore_model_defaults(self):
        tracks=recorded([{'t':0,'v':{'ParamAngleX':8,'key11':1}},{'t':1,'v':{}}])['tracks']
        self.assertEqual({t['id'] for t in tracks},{'AngleX','key11'})
        for track in tracks:
            self.assertEqual(track['points'][-2:],[ [1,0], [1.2,0] ])

    def test_rejects_unknown_channel_and_duplicate_time(self):
        for frames in [[{'t':0,'v':{'unknown':1}},{'t':1,'v':{}}],
                       [{'t':0,'v':{'key11':1}},{'t':0,'v':{}}]]:
            with self.assertRaises(CompileError):recorded(frames)
