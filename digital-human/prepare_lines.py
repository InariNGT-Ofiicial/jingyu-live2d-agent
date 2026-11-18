"""Add missing A3 response recordings without regenerating the accepted bank."""
from pathlib import Path
import argparse,json,requests,wave,hashlib,time
parser=argparse.ArgumentParser();parser.add_argument('--refresh',action='store_true')
args=parser.parse_args()
root=Path(__file__).resolve().parent
from settings import LOCAL, NAME, WORKER
bank=LOCAL/'audio'
bank.mkdir(parents=True,exist_ok=True)
manifest=bank/'manifest.json'
records=json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else []
known={x['id']:x for x in records}
for p in json.loads((root/'dialogue-bank.json').read_text(encoding='utf-8').replace('DeepseekChan',NAME)):
 for i,line in enumerate(p['lines']):
  key=p['id']+'-'+str(i)
  f=bank/(key+'.wav')
  if not args.refresh and key in known and known[key]['text']==line and f.is_file():
   if hashlib.sha256(f.read_bytes()).hexdigest()==known[key]['sha256']:continue
  start=time.monotonic();r=requests.post(WORKER+'/speak',json={'text':line},timeout=30);r.raise_for_status()
  if not r.content or len(r.content)%2:raise ValueError('Invalid PCM for '+key)
  temp=f.with_suffix('.part')
  with wave.open(str(temp),'wb') as w:w.setparams((1,2,24000,0,'NONE','not compressed'));w.writeframes(r.content)
  temp.replace(f)
  row=dict(id=key,text=line,voiceId='call-a3',sha256=hashlib.sha256(f.read_bytes()).hexdigest())
  records=[x for x in records if x['id']!=key]+[row]
  pending=manifest.with_suffix('.part')
  pending.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
  pending.replace(manifest)
  print(key,round(time.monotonic()-start,3),flush=True)
