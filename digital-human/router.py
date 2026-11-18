import json,os,re,unicodedata
from pathlib import Path
from urllib.request import Request,urlopen

from settings import NAME
ROOT=Path(__file__).resolve().parent
CATALOG={x['id']:x for x in json.loads((ROOT/'dialogue-bank.json').read_text('utf-8').replace('DeepseekChan',NAME))}
def normal(text):
    text=unicodedata.normalize('NFKC',text.strip()).lower()
    return ''.join(c for c in text if not c.isspace() and not unicodedata.category(c).startswith('P'))
ALIASES={normal(s):k for k,p in CATALOG.items() for s in p['aliases']}
CALLSIGN=normal(NAME)

def addressed_match(aliases,text):
    n=normal(text)
    return aliases.get(n) or aliases.get(n.removeprefix(CALLSIGN))

def select(text,history,use_jev):
    direct=addressed_match(ALIASES,text)
    if direct:return direct,'exact'
    if not use_jev:return None,'local_fallback'
    criteria={k:r['description'] for k,r in CATALOG.items() if not r.get('exact_only')}
    criteria['other']='新信息、连续追问、多意图或预设无法完整回答'
    payload=dict(model='jev-1.14.0',state=dict(input=text,recent=history[-3:]),questions={
        'intent':dict(type='choice',instructions='选择能完整回应这条输入的意图，否则选 other。',criteria=criteria),
        'covered':dict(type='noul',instructions='仅用一种候选寒暄台词，能否完整回答当前输入？涉及个人记忆、追问或实质问题选否。')})
    req=Request('https://api.typesafe.ai/v1/systemone',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+os.environ['TYPESAFE_API_KEY'],'Content-Type':'application/json'})
    try:
        with urlopen(req,timeout=.65) as r:ans=json.load(r)['answers']
        c=ans['intent']; valid=(c['type']=='choice' and c['choice'] in CATALOG and .80<=float(c['confidence'])<=1 and ans['covered']['type']=='noul' and 0.85<=float(ans['covered']['noul'])<=1)
        return (c['choice'],'jev') if valid else (None,'jev_abstain')
    except (OSError,ValueError,KeyError,TypeError):return None,'jev_unavailable'
