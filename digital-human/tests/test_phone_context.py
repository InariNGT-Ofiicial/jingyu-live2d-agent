import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from phone_context import phone_messages,speech_parts,needs_detail


class PhoneContext(unittest.TestCase):
    def test_earlier_constraint_survives_interruption(self):
        history=[dict(text='只有手机',reply='那就用手机拍。')]
        history += [dict(text='镜头拉远一点呢？',reply='可以试试。') for _ in range(4)]
        history.append(dict(text='我说的是室内',reply='',interrupted=True))
        turns=phone_messages('怎么补光？',history)
        self.assertTrue(any('只有手机' in row['content'] for row in turns))
        self.assertIn('室内',turns[-1]['content'])
        self.assertIn('怎么补光',turns[-1]['content'])

    def test_long_answer_is_preserved_in_order_across_voice_requests(self):
        reply='先把台灯移到左边。然后打开手机相机，对焦在人脸上。最后退后两步，避开玻璃上的反光。'
        self.assertEqual(''.join(speech_parts(reply)),reply)
        self.assertGreater(len(speech_parts(reply)),1)
        self.assertTrue(needs_detail('周末去露营要注意什么？'))
        self.assertFalse(needs_detail('一句话解释为什么。'))
        self.assertLessEqual(max(map(len,speech_parts('啊'*350))),140)

    def test_latest_correction_is_grounded_and_topic_switch_discards_it(self):
        h=[dict(text='约在东门',reply='好。'),dict(text='改到西门。',reply='好。')]
        h += [dict(text='我会带伞。',reply='嗯。') for _ in range(11)]
        self.assertIn('西门',phone_messages('最后约在哪里？',h)[-1]['content'])
        self.assertNotIn('西门',str(phone_messages('换个话题，晚饭吃什么？',h)))
