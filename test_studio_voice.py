import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from studio_voice import Voice

class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.voice=Voice(self.temp.name)
    def test_missing_config_is_explicit(self):
        self.assertFalse(self.voice.state()['ready'])
    def test_no_path_traversal_or_pending_audio(self):
        for jid in ['../secrets','a'*11,None]:
            with self.assertRaises(ValueError):self.voice.audio(jid)
        folder=self.voice.folder/('a'*12);folder.mkdir(parents=True)
        (folder/'status.json').write_text(json.dumps({'status':'synthesizing'}))
        self.assertEqual(self.voice.get('a'*12)['status'],'error')
        with self.assertRaises(ValueError):self.voice.audio('a'*12)
    def test_reject_empty_or_overlong_text(self):
        for text in ['', 'a'*501, None]:
            with self.assertRaises(ValueError):self.voice.start({'text':text})
    def test_one_inference_at_a_time(self):
        self.voice.running=True
        with patch.object(self.voice,'preset',return_value=(Path('preset.json'),{'params':{'instruction':'自然'}})):
            with self.assertRaisesRegex(ValueError,'已有语音'):self.voice.start({'text':'你好'})
    def test_saved_takes_survive_new_instance(self):
        folder=self.voice.folder/('b'*12);folder.mkdir(parents=True)
        (folder/'status.json').write_text(json.dumps({'id':'b'*12,'status':'ready','text':'hello'}))
        restored=Voice(self.temp.name).state()['takes']
        self.assertEqual(restored[0]['text'],'hello')
    def test_portable_preset_resolves_from_workbench_not_cwd(self):
        root=Path(self.temp.name);voice=root/'voice';voice.mkdir()
        python=root/'runtime/python.exe';python.parent.mkdir();python.touch()
        (voice/'preset.json').write_text(json.dumps({'engine':{'python':'../runtime/python.exe',
            'project':'.','model_dir':'models'},'reference':{'file':'reference.wav'}}))
        (root/'.local').mkdir()
        (root/'.local/studio-voice.json').write_text('{"preset":"voice/preset.json"}')
        path,preset=self.voice.preset()
        self.assertEqual(path,voice/'preset.json')
        self.assertEqual(Path(preset['engine']['python']),python)
        self.assertEqual(Path(preset['engine']['project']),voice)
        self.assertEqual(Path(preset['engine']['model_dir']),voice/'models')

if __name__=='__main__':unittest.main()
