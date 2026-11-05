import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studio_voice_stream import StreamingVoice
from voice_segments import Segments


class StreamTests(unittest.TestCase):
    def test_incremental_segments_preserve_content_and_decimal(self):
        text = '今天我们来试试流式语音，圆周率是3.14。后面的台词正在陆续到达。再见。'
        segmenter = Segments()
        parts = []
        for char in text:
            parts += segmenter.feed(char)
        parts += segmenter.feed('', done=True)
        self.assertEqual(''.join(parts), text)
        self.assertIn('3.14', parts[0])
        self.assertEqual(parts[-1][-3:], '再见。')

    def test_no_punctuation_is_bounded_and_tail_flushes(self):
        segmenter = Segments()
        self.assertEqual([len(s) for s in segmenter.feed('字'*181)], [80, 80])
        self.assertEqual(segmenter.feed('', True), ['字'*21])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.voice = StreamingVoice(self.temp.name)
        self.sent = []
        for name, kwargs in [('preset', {'return_value': (Path('preset'), {'params': {'instruction': '自然'}})}),
                             ('warmup', {'return_value': {'status': 'ready'}}),
                             ('_send', {'side_effect': self.sent.append})]:
            patcher = patch.object(self.voice, name, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.voice.folder.mkdir(parents=True)

    def test_incremental_end_and_saved_text(self):
        job = self.voice.begin({})
        self.voice.append({'id': job['id'], 'text': '你好。'})
        self.assertEqual([x['type'] for x in self.sent], ['begin'])
        self.voice.append({'id': job['id'], 'text': '接下来是第二句话。', 'done': True})
        self.assertEqual([x['type'] for x in self.sent], ['begin', 'segment', 'end'])
        self.assertEqual(self.voice.get(job['id'])['text'], '你好。接下来是第二句话。')
        with self.assertRaises(ValueError):
            self.voice.append({'id': job['id'], 'text': '迟到的文字'})

    def test_cancel_ends_stream_but_reserves_worker_until_drain(self):
        job = self.voice.begin({})
        self.voice.cancel(job['id'])
        self.assertEqual(list(self.voice.events(job['id']))[-1]['type'], 'cancelled')
        self.assertEqual(self.voice.get(job['id'])['status'], 'cancelled')
        with self.assertRaises(ValueError):
            self.voice.begin({'text': '新任务', 'inputComplete': True})
        with self.assertRaises(ValueError):
            self.voice.append({'id': job['id'], 'text': '不该再合成'})

    def test_oversize_append_does_not_change_text(self):
        job = self.voice.begin({'text': '你好'})
        with self.assertRaises(ValueError):
            self.voice.append({'id': job['id'], 'text': '字'*500})
        self.assertEqual(self.voice.get(job['id'])['text'], '你好')
        self.voice.cancel(job['id'])

    def test_style_persisted_and_instruction_override(self):
        job = self.voice.begin({'performance': {'emotion': 'happy', 'intensity': .8}, 'instruction': '自定义'})
        saved = self.voice.get(job['id'])
        self.assertEqual(saved['performance'], {'emotion': 'happy', 'intensity': .8, 'motion': True})
        self.assertEqual(saved['instruction'], '自定义')
        self.voice.cancel(job['id'])

    def test_invalid_style_rejected_before_start(self):
        for settings in [{'emotion': []}, {'intensity': float('nan')}, {'motion': 'false'}, []]:
            with self.assertRaises(ValueError):
                self.voice.begin({'performance': settings})
        self.assertFalse(self.voice.running)


if __name__ == '__main__':
    unittest.main()
