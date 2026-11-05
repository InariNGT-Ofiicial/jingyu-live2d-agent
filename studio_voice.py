"""Small asynchronous adapter for a locally configured DS CosyVoice preset."""
import json,os,subprocess,threading,time,uuid
from pathlib import Path
from copy import deepcopy

def load_preset(path):
    path=Path(path).resolve()
    preset=json.loads(path.read_text(encoding='utf-8-sig'))
    for key in ('python','project','model_dir'):
        value=Path(preset['engine'][key])
        preset['engine'][key]=str((path.parent/value).resolve() if not value.is_absolute() else value)
    return preset

def voice_environment(preset):
    env={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8','PYTHONNOUSERSITE':'1',
         'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'}
    project=Path(preset['engine']['project'])
    if (project/'wetext_models').is_dir():env['WETEXT_MODELS_DIR']=str(project/'wetext_models')
    runtime=Path(preset['engine']['python']).parent
    bins=[runtime,runtime/'Library/bin',Path(__file__).parent/'runtime/ffmpeg']
    env['PATH']=os.pathsep.join(str(p) for p in bins if p.is_dir())+os.pathsep+env.get('PATH','')
    return env

class Voice:
    def __init__(self,root):
        self.root=Path(root);self.folder=self.root/'.local/studio-voice'
        self.lock=threading.RLock();self.running=False
    def preset(self):
        cfg=self.root/'.local/studio-voice.json'
        if not cfg.exists():raise ValueError('尚未配置本地 DS 声线：.local/studio-voice.json')
        path=Path(json.loads(cfg.read_text(encoding='utf-8-sig'))['preset'])
        if not path.is_absolute():path=self.root/path
        path=path.resolve()
        p=load_preset(path)
        if not Path(p['engine']['python']).is_file():raise ValueError('CosyVoice Python 环境不存在')
        return path,p
    def state(self):
        try:
            _,p=self.preset();config={'ready':True,'voice':p['character'],'presetId':p['id'],'engine':p['engine']['name']}
        except (ValueError,OSError,KeyError) as e:config={'ready':False,'error':str(e)}
        with self.lock:
            takes=[]
            for path in sorted(self.folder.glob('*/status.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:50]:
                try:takes.append(self.get(path.parent.name))
                except (ValueError,OSError):continue
            return {**config,'running':self.running,'takes':takes}
    def get(self,jid):
        if not isinstance(jid,str) or len(jid)!=12 or any(c not in '0123456789abcdef' for c in jid):raise ValueError('无效语音编号')
        path=self.folder/jid/'status.json'
        if not path.exists():raise ValueError('语音任务不存在')
        with self.lock:
            job=json.loads(path.read_text(encoding='utf-8'))
            if job['status']=='synthesizing' and not self.running:
                job.update(status='error',error='服务重启中断了合成，请重新生成')
            return job
    def audio(self,jid):
        job=self.get(jid)
        if job['status']!='ready':raise ValueError('语音尚未合成完成')
        return self.folder/jid/'speech.wav'
    def start(self,data):
        text=data.get('text')
        if not isinstance(text,str) or not 1<=len(text.strip())<=500:raise ValueError('台词需要 1..500 字')
        path,p=self.preset();instruction=data.get('instruction') or p['params']['instruction']
        if not isinstance(instruction,str) or len(instruction)>300:raise ValueError('语气指令过长')
        with self.lock:
            if self.running:raise ValueError('已有语音正在合成，请稍候')
            jid=uuid.uuid4().hex[:12];folder=self.folder/jid;folder.mkdir(parents=True)
            job={'id':jid,'status':'synthesizing','text':text.strip(),'instruction':instruction,'createdAt':time.time()}
            status=folder/'status.json'
            status.write_text(json.dumps(job,ensure_ascii=False),encoding='utf-8')
            request={'preset':str(path),'text':job['text'],'instruction':instruction,'output':str(folder/'speech.wav'),'result':str(folder/'result.json')}
            (folder/'request.json').write_text(json.dumps(request,ensure_ascii=False),encoding='utf-8')
            self.running=True
        def worker():
            try:
                env=voice_environment(p)
                with (folder/'worker.log').open('w',encoding='utf-8') as log:
                    proc=subprocess.run([p['engine']['python'],str(self.root/'studio_voice_worker.py'),str(folder/'request.json')],
                        cwd=p['engine']['project'],env=env,stdout=log,stderr=log,timeout=600,
                        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                if proc.returncode:raise ValueError('CosyVoice 合成失败，请查看 .local/studio-voice/'+jid+'/worker.log')
                result=json.loads((folder/'result.json').read_text(encoding='utf-8'))
                job.update(status='ready',audioUrl='/api/studio/voice/audio?id='+jid,**result)
            except Exception as e:job.update(status='error',error=str(e))
            finally:
                with self.lock:
                    status.write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf-8');self.running=False
        threading.Thread(target=worker,daemon=True).start()
        return deepcopy(job)
