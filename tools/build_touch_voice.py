"""Generate reusable interaction clips through the configured local resident voice API."""
import hashlib
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'web/assets/touch-voice'
BASE='http://127.0.0.1:61944'


def api(route,data=None):
    req=Request(BASE+route,data=json.dumps(data,ensure_ascii=False).encode() if data is not None else None,
                headers={'Content-Type':'application/json'})
    with urlopen(req,timeout=15) as r:return json.load(r)


catalog=json.loads((DEST/'catalog.json').read_text(encoding='utf-8'))
manifest_path=DEST/'manifest.json'
manifest=json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {'voice':catalog['voice'],'clips':{}}
for line in catalog['clips']:
    target=DEST/(line['id']+'.wav')
    old=manifest['clips'].get(line['id'],{})
    if old.get('text')==line['text'] and old.get('instruction')==line['instruction'] and target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()==old.get('audioSha256'):
        continue
    job=api('/api/studio/voice',{'text':line['text'],'instruction':line['instruction']})
    for _ in range(180):
        job=api('/api/studio/voice?id='+job['id'])
        if job['status']!='synthesizing':break
        time.sleep(.5)
    if job['status']!='ready':raise RuntimeError(job)
    with urlopen(BASE+job['audioUrl'],timeout=15) as r:audio=r.read()
    target.write_bytes(audio)
    manifest['clips'][line['id']]={**line,'file':target.name,'duration':job['duration'],
        'takeId':job['id'],'referenceSha256':job['referenceSha256'],'audioSha256':hashlib.sha256(audio).hexdigest()}
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'clip':line['id'],'duration':job['duration'],'emotion':line['emotion']},ensure_ascii=False),flush=True)
