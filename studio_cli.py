"""CLI/HTTP transport for deterministic studio tools."""
import argparse, json, os
from urllib.request import Request, urlopen
from urllib.error import HTTPError

def request(path, payload=None):
    base=os.getenv('JINGYU_STUDIO_URL','http://127.0.0.1:61944').rstrip('/')
    req=Request(base+path,headers={'Content-Type':'application/json'},
        data=json.dumps(payload).encode() if payload is not None else None)
    try:
        with urlopen(req,timeout=25) as response:return json.load(response)
    except HTTPError as e:
        try:message=json.load(e).get('error',str(e))
        except ValueError:message=str(e)
        raise ValueError(message) from e

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation',choices=['state','set','play','stop','obs','speak','voice','voice-warmup','voice-start','voice-append','voice-cancel','danmaku','danmaku-claim','danmaku-reply','danmaku-stop','minecraft'])
    p.add_argument('--game-action',choices=['start','inspect','walk','dig','place','demo','stop','shutdown','survival','survival-step'])
    p.add_argument('--world',choices=['demo','survival'],default='survival')
    p.add_argument('--goal',choices=['starter','sustain','return-home'],default='starter')
    p.add_argument('--max-steps',type=int,default=160)
    p.add_argument('--max-minutes',type=float,default=15)
    p.add_argument('--block',choices=['oak_log','stone'],default='oak_log')
    p.add_argument('--message-id',help='要回复的弹幕 ID')
    p.add_argument('--done',action='store_true',help='本轮台词已全部送完')
    p.add_argument('--text',help='合成 DS 娘台词；省略则读取声线状态')
    p.add_argument('--instruction',default='')
    p.add_argument('--emotion',choices=['auto','neutral','happy','gentle','curious','shy','serious'],default='auto')
    p.add_argument('--intensity',type=float,default=.65)
    p.add_argument('--speech-id',help='voice 查询合成；play 播放已合成语音')
    p.add_argument('--client');p.add_argument('--theme',choices=['warm','cool'])
    p.add_argument('--scene',choices=['study-v2','classic','minecraft']);p.add_argument('--camera',choices=['wide','close'])
    p.add_argument('--plan',help='version:1 动作计划 JSON 文件');p.add_argument('--silent',action='store_true')
    p.add_argument('--obs-action',choices=['status','switch','record','stop'],default='status')
    p.add_argument('--obs-scene')
    a=p.parse_args()
    try:
        if a.operation=='state':result=request('/api/studio/state')
        elif a.operation=='minecraft':result=request('/api/minecraft',{'action':a.game_action,'block':a.block,'clientId':a.client,'world':a.world,'goal':a.goal,'maxSteps':a.max_steps,'maxMinutes':a.max_minutes}) if a.game_action else request('/api/minecraft')
        elif a.operation=='speak':result=request('/api/studio/speak',{'text':a.text,'clientId':a.client,'instruction':a.instruction,'performance':{'emotion':a.emotion,'intensity':a.intensity}})
        elif a.operation=='danmaku':result=request('/api/studio/danmaku')
        elif a.operation=='danmaku-claim':result=request('/api/studio/danmaku/claim',{})
        elif a.operation=='danmaku-reply':result=request('/api/studio/danmaku/reply',{'id':a.message_id,'text':a.text})
        elif a.operation=='danmaku-stop':result=request('/api/studio/danmaku/stop',{})
        elif a.operation=='voice-warmup':result=request('/api/studio/voice/warmup',{})
        elif a.operation=='voice-start':result=request('/api/studio/voice/start',{'text':a.text or '', 'instruction':a.instruction,'inputComplete':a.done,'performance':{'emotion':a.emotion,'intensity':a.intensity}})
        elif a.operation=='voice-append':result=request('/api/studio/voice/append',{'id':a.speech_id,'text':a.text or '', 'done':a.done})
        elif a.operation=='voice-cancel':result=request('/api/studio/voice/cancel',{'id':a.speech_id})
        elif a.operation=='voice':
            from urllib.parse import urlencode
            result=request('/api/studio/voice',{'text':a.text,'instruction':a.instruction,'performance':{'emotion':a.emotion,'intensity':a.intensity}}) if a.text else request('/api/studio/voice?'+urlencode({'id':a.speech_id or ''}))
        elif a.operation=='obs':result=request('/api/studio/obs',{'action':a.obs_action,'scene':a.obs_scene})
        else:
            data={'action':a.operation,'clientId':a.client}
            if a.operation=='set':data['scene']={k:v for k,v in {'id':a.scene,'theme':a.theme,'camera':a.camera}.items() if v}
            if a.operation=='play':
                data['audio']='silent' if a.silent else 'greeting'
                if a.speech_id:data.update(audio='speech',speechId=a.speech_id)
                if a.plan:
                    from pathlib import Path
                    data['plan']=json.loads(Path(a.plan).read_text(encoding='utf-8-sig'))
            result=request('/api/studio/command',data)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except Exception as e:p.exit(1,str(e)+'\n')
