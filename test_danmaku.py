import unittest
from studio_danmaku import Danmaku


class FakeVoice:
    running = False
    def begin(self, data):
        self.running = True
        return {'id': 'voice', 'streamUrl': '/stream'}
    def cancel(self, jid):
        self.running = False


class FakeStudio:
    def state(self):
        return {'clients': [{'id': 'stage', 'ready': True}]}


class DanmakuTests(unittest.TestCase):
    def setUp(self):
        self.events=[]
        self.voice=FakeVoice()
        self.chat=Danmaku(self.voice, FakeStudio(), lambda k,v:self.events.append((k,v)))
        self.chat.start({'clientId':'stage','minInterval':60,'maxInterval':60,'count':1})
        self.addCleanup(self.chat.stop)

    def test_replies_wait_for_actual_playback_receipt(self):
        a=self.chat.push({'text':'你好'})
        b=self.chat.push({'text':'还在吗'})
        self.assertEqual(self.chat.claim()['message']['id'],a['id'])
        self.chat.reply({'id':a['id'],'text':'你好，我能看到你的弹幕。'})
        self.voice.running=False  # Synthesis finished, but browser is still playing.
        self.assertIsNone(self.chat.claim()['message'])
        self.chat.report({'id':a['id'],'clientId':'stage','status':'done'})
        next_message=self.chat.claim()
        self.assertEqual(next_message['message']['id'],b['id'])
        self.assertEqual(next_message['context'][0]['reply'],'你好，我能看到你的弹幕。')

    def test_duplicate_reply_rejected_and_stop_cancels_queue(self):
        message=self.chat.push({'text':'测试'})
        self.chat.claim();self.chat.reply({'id':message['id'],'text':'收到。'})
        with self.assertRaises(ValueError):self.chat.reply({'id':message['id'],'text':'重复'})
        self.chat.push({'text':'等待消息'})
        state=self.chat.stop()
        self.assertTrue(all(m['status']=='cancelled' for m in state['messages']))
        self.assertFalse(self.voice.running)
        with self.assertRaises(ValueError):self.chat.push({'text':'停止后不应进入'})

    def test_burst_is_bounded_without_losing_active_message(self):
        active=self.chat.push({'text':'正在处理'})
        self.chat.claim()
        for i in range(60):self.chat.push({'text':str(i)})
        state=self.chat.state()
        self.assertEqual(state['queued'],8)
        self.assertIn(active['id'],[m['id'] for m in state['messages']])
        self.assertEqual(state['messages'][-1]['status'],'skipped')


if __name__=='__main__':unittest.main()
