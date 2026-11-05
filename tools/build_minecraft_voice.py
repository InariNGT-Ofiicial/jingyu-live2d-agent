"""Cache truthful short game event narration using the configured DS voice."""
import json,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from studio_cli import request

ROOT=Path(__file__).resolve().parents[1]
catalog=json.loads((ROOT/'minecraft/cues.json').read_text(encoding='utf-8'))
destination=ROOT/'.local/minecraft/cues.json'
destination.parent.mkdir(parents=True,exist_ok=True)
saved=json.loads(destination.read_text(encoding='utf-8')) if destination.exists() else {}
for key,cue in catalog.items():
    old=saved.get(key,{})
    if old.get('text')==cue['text'] and old.get('emotion')==cue['emotion']:
        try:
            if request('/api/studio/voice?id='+old['speechId'])['status']=='ready':continue
        except ValueError:pass
    job=request('/api/studio/voice',{'text':cue['text'],'performance':{'emotion':cue['emotion'],'intensity':.45}})
    for _ in range(240):
        job=request('/api/studio/voice?id='+job['id'])
        if job['status']!='synthesizing':break
        time.sleep(.5)
    if job['status']!='ready':raise RuntimeError(job.get('error','Voice timeout'))
    saved[key]={**cue,'speechId':job['id'],'duration':job['duration']}
    destination.write_text(json.dumps(saved,ensure_ascii=False,indent=2),encoding='utf-8')
    print(key,job['duration'],flush=True)
