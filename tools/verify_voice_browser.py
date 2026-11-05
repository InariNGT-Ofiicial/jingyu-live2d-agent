"""Exercise the real studio page through a dedicated local Chromium CDP port."""
import base64
import json
from pathlib import Path
import sys
import time
from urllib.request import Request, urlopen
import websocket

BASE = 'http://127.0.0.1:61944'
OUT = Path(__file__).resolve().parents[1]/'.local/checks/voice-stream'
OUT.mkdir(parents=True, exist_ok=True)


def api(route, data=None):
    req = Request(BASE+route, data=json.dumps(data).encode() if data is not None else None,
                  headers={'Content-Type': 'application/json'})
    with urlopen(req, timeout=10) as r:
        return json.load(r)


with urlopen('http://127.0.0.1:61949/json/list') as r:
    tab = next(t for t in json.load(r) if t.get('url') == BASE+'/scene-experiment.html')
socket = websocket.create_connection(tab['webSocketDebuggerUrl'], timeout=15, suppress_origin=True)
seq = 0


def cdp(method, params=None):
    global seq
    seq += 1
    socket.send(json.dumps({'id': seq, 'method': method, 'params': params or {}}))
    while True:
        message = json.loads(socket.recv())
        if message.get('id') == seq:
            if 'error' in message:
                raise RuntimeError(message['error'])
            return message['result']


def js(expression):
    result = cdp('Runtime.evaluate', {'expression': expression, 'returnByValue': True, 'userGesture': True})
    if 'exceptionDetails' in result:
        raise RuntimeError(result['exceptionDetails'])
    return result.get('result', {}).get('value')


def until(fn, timeout=120):
    end = time.monotonic()+timeout
    while time.monotonic() < end:
        value = fn()
        if value:
            return value
        time.sleep(.2)
    raise TimeoutError('Browser/API check timed out')


try:
    cdp('Emulation.setDeviceMetricsOverride', {'width': 1500, 'height': 1000, 'deviceScaleFactor': 1, 'mobile': False})
    cdp('Page.bringToFront')
    cdp('Page.reload', {'ignoreCache': True})
    until(lambda: js('window.sceneExperiment?.status().ready'))
    api('/api/studio/voice/warmup', {})
    until(lambda: api('/api/studio/voice')['engineState']['status'] == 'ready')
    print('model and renderer ready', flush=True)
    js('void window.sceneExperiment.voice.start(true)')
    jid = until(lambda: js('window.sceneExperiment.voice.status().id'), 10)
    parts = ['你好，我是晓伊。', '今天我们来试试工作台的实时语音，', '文字到达后，我会逐段说出来。',
             '你可以看见我的嘴型和字幕，', '也可以随时让我停下来。']
    for i, part in enumerate(parts):
        api('/api/studio/voice/append', {'id': jid, 'text': part, 'done': i == len(parts)-1})
        time.sleep(.7)
    samples = []
    def ended():
        sample = js('({...window.sceneExperiment.voice.status(),caption:document.querySelector("#caption").textContent})')
        samples.append(sample)
        return not sample.get('id')
    until(ended)
    take = api('/api/studio/voice?id='+jid)
    (OUT/'playback-trace.json').write_text(json.dumps(samples, ensure_ascii=False), encoding='utf-8')
    assert take['status'] == 'ready', take
    assert any(s.get('playedSamples', 0) > 0 for s in samples), 'No actual playback'
    assert max(s.get('mouth', 0) for s in samples) > .02, 'No lip sync'
    captions = list(dict.fromkeys(s['caption'] for s in samples if s['caption']))
    assert len(captions) >= 2, captions
    with urlopen(BASE+take['audioUrl']) as r:
        assert len(r.read()) > 1000
    print('incremental PCM, mouth, captions and WAV passed', flush=True)
    js('document.querySelector("#speech-text").value="这一段台词用来测试中途停止，停止之后不应该继续播放旧的声音，也不应该污染下一次合成。"; void window.sceneExperiment.voice.start(false)')
    cancelled = until(lambda: js('window.sceneExperiment.voice.status().id'), 10)
    until(lambda: js('window.sceneExperiment.voice.status().playedSamples>0'), 60)
    js('window.sceneExperiment.voice.stop()')
    assert not js('!!window.sceneExperiment.voice.status().active')
    until(lambda: api('/api/studio/voice?id='+cancelled)['status'] == 'cancelled', 10)
    until(lambda: not api('/api/studio/voice')['running'], 45)
    js('document.querySelector("#speech-text").value="已经停好了，现在开始新的一句。"; void window.sceneExperiment.voice.start(false)')
    next_id = until(lambda: js('window.sceneExperiment.voice.status().id'), 10)
    until(lambda: not js('window.sceneExperiment.voice.status().id'), 60)
    assert api('/api/studio/voice?id='+next_id)['status'] == 'ready'
    js('document.querySelector("#speech-play").click()')
    until(lambda: js('window.sceneExperiment.status().playing'), 10)
    js('window.sceneExperiment.stop()')
    until(lambda: not js('window.sceneExperiment.status().playing'), 10)
    js('document.querySelector("#live-voice").scrollIntoView({block:"center"})')
    time.sleep(.3)
    png = cdp('Page.captureScreenshot', {'format': 'png'})['data']
    (OUT/'page.png').write_bytes(base64.b64decode(png))
    report = {'take': take, 'cancelledId': cancelled, 'nextId': next_id, 'captions': captions,
              'maxMouth': max(s.get('mouth', 0) for s in samples),
              'underrunBlocks': max(s.get('underrunBlocks', 0) for s in samples),
              'checks': ['stream-play', 'lip-sync', 'subtitles', 'wav', 'cancel', 'reuse', 'replay']}
    (OUT/'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)
finally:
    socket.close()
