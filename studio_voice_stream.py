"""Resident voice bridge with bounded takes, incremental text, and replayable PCM events."""
import atexit
from copy import deepcopy
import json
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path

from studio_voice import Voice, voice_environment
from voice_segments import Segments

TERMINAL = {'ready', 'cancelled', 'error'}
STYLES = json.loads((Path(__file__).parent/'web/data/speech-styles.json').read_text(encoding='utf-8'))


def performance_settings(data):
    value = data.get('performance', {})
    if not isinstance(value, dict):
        raise ValueError('performance 需要对象')
    emotion, intensity, motion = value.get('emotion', 'auto'), value.get('intensity', .65), value.get('motion', True)
    if not isinstance(emotion, str) or emotion not in STYLES or type(intensity) not in (int, float) or not 0 <= intensity <= 1 or type(motion) is not bool:
        raise ValueError('表演设置无效：需要有效 emotion、0..1 intensity 和布尔 motion')
    return {'emotion': emotion, 'intensity': intensity, 'motion': motion}


class StreamingVoice(Voice):
    def __init__(self, root):
        super().__init__(root)
        self.changed = threading.Condition(self.lock)
        self.process = None
        self.engine = {'status': 'unloaded'}
        self.sessions = {}
        self.active_id = None
        atexit.register(self.close)

    def state(self):
        with self.lock:
            return {**super().state(), 'streaming': True, 'engineState': deepcopy(self.engine),
                    'activeId': self.active_id, 'startupBufferSeconds': 3}

    def close(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                try:
                    self.process.stdin.close()
                except OSError:
                    pass

    def _send(self, event):
        try:
            self.process.stdin.write(json.dumps(event, ensure_ascii=False) + '\n')
            self.process.stdin.flush()
        except (OSError, AttributeError, ValueError):
            raise ValueError('语音进程已退出，请重试加载') from None

    def warmup(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                return deepcopy(self.engine)
            path, preset = self.preset()
            self.folder.mkdir(parents=True, exist_ok=True)
            self.engine = {'status': 'loading'}
            env = voice_environment(preset)
            with (self.folder/'resident.log').open('a', encoding='utf-8') as log:
                proc = subprocess.Popen([preset['engine']['python'], '-u',
                    str(self.root/'studio_voice_stream_worker.py'), str(path), str(self.folder/'numba-cache')],
                    cwd=preset['engine']['project'], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=log, text=True, encoding='utf-8', bufsize=1,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.process = proc
            threading.Thread(target=self._read, args=(proc,), daemon=True).start()
            return deepcopy(self.engine)

    def _save(self, session):
        job = session['job']
        (self.folder/job['id']/'status.json').write_text(
            json.dumps(job, ensure_ascii=False, indent=2), encoding='utf-8')

    def _event(self, session, event):
        event = {**event, 'seq': len(session['events']),
                 'elapsed': time.monotonic()-session['started']}
        session['events'].append(event)
        self.changed.notify_all()

    def _read(self, proc):
        try:
            for line in proc.stdout:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                with self.lock:
                    if proc is not self.process:
                        return
                    if event['type'] == 'engine':
                        self.engine = event
                        continue
                    session = self.sessions.get(event.get('id'))
                    if not session:
                        continue
                    job = session['job']
                    kind = event['type']
                    if kind in ('released', 'done', 'error'):
                        if self.active_id == job['id']:
                            self.running = False
                            self.active_id = None
                    if job['status'] in TERMINAL:
                        continue
                    if kind == 'pcm':
                        job.setdefault('firstAudioSeconds', time.monotonic()-session['started'])
                    if kind == 'segment':
                        job['segments'].append({k:event[k] for k in ('text','offsetSamples')})
                    if kind == 'done':
                        job.update(status='ready', audioUrl='/api/studio/voice/audio?id='+job['id'],
                                   **{k: v for k, v in event.items() if k not in ('id', 'type')})
                        event['audioUrl'] = job['audioUrl']
                    elif kind == 'error':
                        job.update(status='error', error=event['error'])
                    self._event(session, event)
                    if kind != 'pcm':
                        self._save(session)
        finally:
            proc.wait()
            with self.lock:
                if proc is self.process:
                    self.engine = {'status': 'error', 'error': '语音进程已退出；可重新加载，详情见 resident.log'}
                    if self.active_id:
                        session = self.sessions[self.active_id]
                        if session['job']['status'] not in TERMINAL:
                            session['job'].update(status='error', error=self.engine['error'])
                            self._event(session, {'type': 'error', 'error': self.engine['error']})
                            self._save(session)
                    self.running = False
                    self.active_id = None

    def start(self, data):
        # Preserve the original complete-text API and history behavior.
        return self.begin({**data, 'inputComplete': True})

    def begin(self, data):
        text = data.get('text', '')
        complete = data.get('inputComplete', False)
        if not isinstance(text, str) or len(text) > 500 or (complete and not text.strip()):
            raise ValueError('台词需要 1..500 字；增量会话可以先留空')
        if type(complete) is not bool:
            raise ValueError('inputComplete 必须为布尔值')
        performance = performance_settings(data)
        _, preset = self.preset()
        instruction = data.get('instruction') or STYLES[performance['emotion']]['instruction'] or preset['params']['instruction']
        if not isinstance(instruction, str) or len(instruction) > 300:
            raise ValueError('语气指令过长')
        with self.lock:
            if self.running:
                raise ValueError('已有语音正在合成或收尾，请稍候')
            self.warmup()
            jid = uuid.uuid4().hex[:12]
            folder = self.folder/jid
            folder.mkdir()
            job = {'id': jid, 'status': 'synthesizing', 'streaming': True, 'text': '',
                   'instruction': instruction, 'performance': performance, 'segments': [], 'createdAt': time.time(), 'inputComplete': False,
                   'streamUrl': '/api/studio/voice/stream?id='+jid}
            session = {'job': job, 'events': [], 'segments': Segments(), 'started': time.monotonic(),
                       'lastInput': time.monotonic()}
            self.sessions[jid] = session
            # PCM replay is kept for recent takes only; WAV history remains on disk.
            for old in list(self.sessions)[:-8]:
                del self.sessions[old]
            self.running = True
            self.active_id = jid
            self._save(session)
            try:
                self._send({'type': 'begin', 'id': jid, 'instruction': instruction, 'output': str(folder/'speech.wav')})
                self.append({'id': jid, 'text': text, 'done': complete})
            except ValueError as exc:
                job.update(status='error', error=str(exc))
                self._save(session)
                self.running = False
                self.active_id = None
                raise
            threading.Thread(target=self._input_timeout, args=(jid,), daemon=True).start()
            return deepcopy(job)

    def _input_timeout(self, jid):
        with self.changed:
            while self.active_id == jid:
                session = self.sessions[jid]
                if session['job']['inputComplete'] or session['job']['status'] in TERMINAL:
                    return
                if time.monotonic()-session['lastInput'] > 120:
                    self.cancel(jid, '等待文本超过 120 秒，已停止')
                    return
                self.changed.wait(5)

    def append(self, data):
        jid, text, done = data.get('id'), data.get('text', ''), data.get('done', False)
        if not isinstance(text, str) or type(done) is not bool:
            raise ValueError('text 需要字符串，done 需要布尔值')
        with self.lock:
            session = self.sessions.get(jid)
            if not session or jid != self.active_id:
                raise ValueError('增量语音会话不存在或已结束')
            job = session['job']
            if job['status'] in TERMINAL or job['inputComplete']:
                raise ValueError('该语音已停止接收文本')
            if len(job['text'])+len(text) > 500:
                raise ValueError('本轮台词总长度不能超过 500 字')
            if done and not (job['text']+text).strip():
                raise ValueError('不能完成空台词')
            job['text'] += text
            job['inputComplete'] = done
            session['lastInput'] = time.monotonic()
            for part in session['segments'].feed(text, done):
                self._send({'type': 'segment', 'id': jid, 'text': part})
            if done:
                self._send({'type': 'end', 'id': jid})
            self._save(session)
            self.changed.notify_all()
            return deepcopy(job)

    def cancel(self, jid, reason='已停止'):
        with self.lock:
            session = self.sessions.get(jid)
            if not session:
                raise ValueError('增量语音会话不存在')
            if session['job']['status'] not in TERMINAL:
                session['job'].update(status='cancelled', error=reason)
                self._event(session, {'type': 'cancelled', 'reason': reason})
                self._save(session)
                self._send({'type': 'cancel', 'id': jid})
            return deepcopy(session['job'])

    def check_stream(self, jid):
        with self.lock:
            if jid not in self.sessions:
                raise ValueError('实时流已过期，请从语音历史重播')

    def events(self, jid):
        index = 0
        while True:
            with self.changed:
                session = self.sessions.get(jid)
                if not session:
                    return
                pending = session['events'][index:]
                finished = session['job']['status'] in TERMINAL
                if not pending and not finished:
                    self.changed.wait(5)
                    continue
            for event in pending:
                yield event
                index += 1
            if finished:
                return
