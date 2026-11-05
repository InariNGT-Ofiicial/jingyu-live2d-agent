"""Non-personality scene transport: commands, client telemetry and execution receipts."""
import time, uuid, threading
from copy import deepcopy
from collections import deque

class Studio:
    def __init__(self, emit):
        self.emit=emit
        self.lock=threading.RLock()
        self.clients={}
        self.jobs=deque(maxlen=100)
        self.scene={'id':'study-v2','theme':'warm','camera':'wide'}
    def state(self):
        with self.lock:
            now=time.monotonic()
            live={k:v for k,v in self.clients.items() if now-v['_seen']<8}
            self.clients=live
            for j in self.jobs:
                if j['status'] in ('accepted','preparing','playing') and j['clientId'] is not None and j['clientId'] not in live:
                    j.update(status='error',error='场景客户端离线')
                elif j['status']=='accepted' and now-j['_created']>10:
                    j.update(status='error',error='场景未确认执行')
            return deepcopy({'scene':self.scene,'clients':[{k:v for k,v in c.items() if not k.startswith('_')} for c in live.values()],
                'jobs':[{k:v for k,v in j.items() if not k.startswith('_') and k!='compiled'} for j in self.jobs]})
    def heartbeat(self,data):
        cid=data.get('clientId')
        if not isinstance(cid,str) or not 1<=len(cid)<=80:raise ValueError('需要 clientId')
        with self.lock:
            self.clients[cid]={'id':cid,'_seen':time.monotonic(),'ready':data.get('ready') is True,
                'presentation':'obs' if data.get('presentation')=='obs' else 'web',
                'telemetry':{k:data.get('telemetry',{}).get(k) for k in ['fps','playing','audioTime','jobId','audioReady']}}
        return {'ok':True}
    def command(self,data,compiled=None):
        action=data.get('action')
        if action not in ('set','play','stop','speak'):raise ValueError('action 必须为 set/play/stop/speak')
        with self.lock:
            state=self.state()
            cid=data.get('clientId')
            if action!='set':
                targets=[c for c in state['clients'] if c['ready'] and (c['id']==cid if cid else c['presentation']=='web')]
                if len(targets)!=1:raise ValueError('请指定一个在线且就绪的 clientId')
                cid=targets[0]['id']
            if action=='set':
                changes=data.get('scene',{})
                if not isinstance(changes,dict) or not changes:raise ValueError('需要 scene 设置')
                allowed={'id':['study-v2','classic','minecraft'],'theme':['warm','cool'],'camera':['wide','close']}
                for k,v in changes.items():
                    if k not in allowed or v not in allowed[k]:raise ValueError('无效场景设置: '+str(k))
                self.scene.update(changes)
            if action=='play' and data.get('audio','greeting') not in ('greeting','silent','speech'):raise ValueError('audio 必须为 greeting/silent/speech')
            if action=='play' and data.get('audio')=='speech' and not data.get('speech'):raise ValueError('需要已合成的语音')
            if action=='speak' and not data.get('speech',{}).get('streamUrl'):raise ValueError('需要实时语音会话')
            jid=uuid.uuid4().hex[:12]
            job={'id':jid,'action':action,'clientId':cid,'status':'accepted','_created':time.monotonic(),
                'scene':deepcopy(self.scene),'audio':data.get('audio','greeting'),'compiled':compiled,'speech':data.get('speech')}
            self.jobs.appendleft(job)
            public={k:v for k,v in job.items() if not k.startswith('_')}
        self.emit('studio-command',public)
        return public
    def report(self,data):
        with self.lock:
            job=next((j for j in self.jobs if j['id']==data.get('jobId')),None)
            if not job:raise ValueError('未知命令')
            if data.get('clientId') not in self.clients:raise ValueError('客户端未注册')
            if job['clientId'] and job['clientId']!=data.get('clientId'):raise ValueError('回执客户端不匹配')
            status=data.get('status')
            if status not in ('preparing','playing','completed','interrupted','error'):raise ValueError('无效执行状态')
            if job['status'] in ('completed','interrupted','error'):return {'ok':True,'ignored':True}
            job['status']=status
            if status=='error':job['error']=str(data.get('error','播放失败'))[:500]
            return {'ok':True}
