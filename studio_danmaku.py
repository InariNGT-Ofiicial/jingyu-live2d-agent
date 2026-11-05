"""Local timed chat simulator and serialized agent -> voice -> playback receipts."""
from collections import deque
from copy import deepcopy
import random
import threading
import time
import uuid

SAMPLES = [
    ('晚风', '晚上好，今天直播间的雨声好有氛围。'),
    ('小橘', '你平时喜欢晴天还是雨天？为什么？'),
    ('星河', '刚写完作业，有点累，可以鼓励我一句吗？'),
    ('路过的猫', '你能看到我这条弹幕吗？'),
    ('泡泡', '如果给这个雨夜书房起个名字，你会怎么起？'),
    ('阿蓝', '给第一次来的观众介绍一下你自己吧。'),
    ('布丁', '我今天终于把一直拖着的事情做完了！'),
    ('微光', '我想听一句简短的晚安。'),
    ('小白', '如果窗外突然放晴，你想做什么？'),
    ('柚子', '聊天时你会先听完别人说话吗？'),
]


class Danmaku:
    def __init__(self, voice, studio, emit):
        self.voice, self.studio, self.emit = voice, studio, emit
        self.lock = threading.RLock()
        self.messages = deque(maxlen=40)
        self.running = False
        self.producing = False
        self.client_id = None
        self.active_id = None
        self.stop_event = threading.Event()

    def state(self):
        with self.lock:
            return deepcopy({'running': self.running, 'producing': self.producing,
                'source': 'simulated', 'replySource': 'external-agent', 'clientId': self.client_id,
                'activeId': self.active_id, 'queued': sum(m['status']=='queued' for m in self.messages),
                'messages': list(self.messages)})

    def publish(self):
        self.emit('danmaku', self.state())

    def start(self, data):
        low, high, count = data.get('minInterval', 8), data.get('maxInterval', 14), data.get('count', 6)
        if type(low) not in (int, float) or type(high) not in (int, float) or not 2 <= low <= high <= 60:
            raise ValueError('随机间隔需为 2..60 秒，最小值不大于最大值')
        if type(count) is not int or not 1 <= count <= 20:
            raise ValueError('每轮模拟 1..20 条弹幕')
        cid = data.get('clientId')
        if not any(c['id']==cid and c['ready'] for c in self.studio.state()['clients']):
            raise ValueError('请在就绪的直播间页面启动测试')
        with self.lock:
            if self.running:
                raise ValueError('已有弹幕测试正在运行，请先停止')
            if self.voice.running:
                raise ValueError('请等待当前语音结束再启动弹幕测试')
            self.running = self.producing = True
            self.client_id = cid
            self.active_id = None
            self.messages.clear()
            self.stop_event = event = threading.Event()
            self.publish()
        def produce():
            choices = list(SAMPLES)
            random.shuffle(choices)
            for i in range(count):
                if event.wait(random.uniform(low, high)):
                    return
                with self.lock:
                    if event is not self.stop_event or not self.running:
                        return
                    author, text = choices[i % len(choices)]
                    self.push({'author': author, 'text': text, 'source': 'timer'})
            with self.lock:
                if event is self.stop_event:
                    self.producing = False
                    self.publish()
        threading.Thread(target=produce, daemon=True).start()
        return self.state()

    def push(self, data):
        text, author = data.get('text'), data.get('author', '测试观众')
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 200:
            raise ValueError('弹幕需要 1..200 字')
        if not isinstance(author, str) or not 1 <= len(author.strip()) <= 30:
            raise ValueError('观众名需要 1..30 字')
        with self.lock:
            if not self.running:
                raise ValueError('请先启动弹幕测试')
            pending = sum(m['status']=='queued' for m in self.messages)
            message = {'id': uuid.uuid4().hex[:12], 'author': author.strip(), 'text': text.strip(),
                       'source': 'timer' if data.get('source')=='timer' else 'manual-test',
                       'receivedAt': time.time(), 'status': 'queued' if pending < 8 else 'skipped'}
            if pending >= 8:
                message['error'] = '等待队列已满（8 条）'
            if len(self.messages)==self.messages.maxlen:
                old=next(m for m in self.messages if m['status'] in ('done','error','cancelled','skipped'))
                self.messages.remove(old)
            self.messages.append(message)
            self.publish()
            return deepcopy(message)

    def claim(self):
        with self.lock:
            if not self.running:
                raise ValueError('弹幕测试尚未启动')
            if self.active_id or self.voice.running:
                return {'message': None, 'reason': '上一条回复或语音尚未结束'}
            message = next((m for m in self.messages if m['status']=='queued'), None)
            if not message:
                return {'message': None, 'reason': '等待下一条弹幕'}
            message.update(status='claimed', claimedAt=time.time())
            self.active_id = message['id']
            self.publish()
            history = [{'author': m['author'], 'text': m['text'], 'reply': m['reply']}
                       for m in self.messages if m['status']=='done' and 'reply' in m][-4:]
            return {'message': deepcopy(message), 'context': history,
                    'instruction': '请直接回应这条弹幕，使用自然口语，建议 1..2 句、20..80 字。不要输出动作 JSON。'}

    def reply(self, data):
        text = data.get('text')
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 160:
            raise ValueError('弹幕回复需要 1..160 字')
        with self.lock:
            message = next((m for m in self.messages if m['id']==data.get('id')), None)
            if not self.running or not message or self.active_id != message['id'] or message['status']!='claimed':
                raise ValueError('请先领取待回复弹幕；已处理弹幕不能重复回复')
            if not any(c['id']==self.client_id and c['ready'] for c in self.studio.state()['clients']):
                raise ValueError('目标直播间已离线')
            job = self.voice.begin({'text': text.strip(), 'inputComplete': True})
            message.update(status='replying', reply=text.strip(), replyAt=time.time(), voiceId=job['id'])
            self.publish()
            self.emit('danmaku-speech', {'clientId': self.client_id, 'messageId': message['id'], 'job': job})
            return deepcopy(message)

    def report(self, data):
        status = data.get('status')
        if status not in ('playing', 'done', 'error', 'cancelled'):
            raise ValueError('无效弹幕播放回执')
        with self.lock:
            message = next((m for m in self.messages if m['id']==data.get('id')), None)
            if not message or data.get('clientId') != self.client_id:
                raise ValueError('弹幕或目标直播间不匹配')
            if message['status'] in ('done', 'error', 'cancelled', 'skipped'):
                return {'ok': True, 'ignored': True}
            if status=='playing':
                message.setdefault('playedAt', time.time())
                message['status'] = 'playing'
            else:
                message.update(status=status, finishedAt=time.time())
                if status=='error':
                    message['error'] = str(data.get('error', '播放失败'))[:200]
                if self.active_id==message['id']:
                    self.active_id = None
            self.publish()
            return {'ok': True}

    def stop(self):
        with self.lock:
            self.running = self.producing = False
            self.stop_event.set()
            for message in self.messages:
                if message['status'] in ('queued', 'claimed', 'replying', 'playing'):
                    message.update(status='cancelled', finishedAt=time.time())
                    if message.get('voiceId'):
                        self.voice.cancel(message['voiceId'])
            self.active_id = None
            self.publish()
            self.emit('danmaku-stop', {'clientId': self.client_id})
            return self.state()
