"""Compile arbitrary supported plans to a dedicated VTS model's hot-deployed motion."""
import argparse,copy,hashlib,json,math,shutil,subprocess,time
from pathlib import Path
from model_profile import ROOT,MODEL_ROOT,read_json
from runtime_tools import executable
from vts_client import VTS
from vts_setup import ensure_import
HOTKEY='f02a2c7641e04c4691ef09f95ee1cd2a'
def announce(status,**data):print(json.dumps({'status':status,**data},ensure_ascii=True),flush=True)

def load_model(v,mid):
    deadline=time.monotonic()+20
    while True:
        try:return v.call('ModelLoadRequest',{'modelID':mid})
        except RuntimeError as error:
            if not str(error).startswith('VTS API error 153:') or time.monotonic()>=deadline:raise
            time.sleep(.5)
def wait_model(v,mid):
    end=time.monotonic()+20
    while time.monotonic()<end:
        r=v.call('CurrentModelRequest')
        if r.get('modelLoaded') and r.get('modelID')==mid:return r
        time.sleep(.2)
    raise RuntimeError('VTS 模型重载超时')
def reload_model(v,mid,position):
    # VTS shares a two-second cooldown across all model-load requests.
    time.sleep(2.2)
    load_model(v,'');time.sleep(2.2)
    load_model(v,mid);wait_model(v,mid)
    v.call('MoveModelRequest',{'timeInSeconds':0,'valuesAreRelativeToModel':False,**position})
def deploy(jobfile,cancel,port=8001):
    jobfile=Path(jobfile);job=read_json(jobfile);folder=jobfile.parent;mid=read_json(MODEL_ROOT/'大肥鱼.vtube.json')['ModelID']
    manifest=ensure_import();dest=Path(manifest['destination']).resolve()
    if dest==MODEL_ROOT.resolve() or MODEL_ROOT.resolve() in dest.parents or dest.name!='Jingyu-Author-Comparison':raise ValueError('热部署只允许已导入的专用测试副本')
    configfile=dest/'大肥鱼.vtube.json'
    if read_json(configfile)['ModelID']!=mid:raise ValueError('部署副本模型 ID 不匹配')
    announce('compiling',progress=0)
    compiled=folder/'compiled.json';compiled.write_text(json.dumps(job['compiled'],ensure_ascii=False),encoding='utf-8')
    motion=folder/f'Jingyu-Auto-{job["id"]}.motion3.json'
    subprocess.run([executable('node'),str(ROOT/'export_vts_motion.mjs'),str(compiled),str(motion)],check=True,capture_output=True,timeout=90)
    if cancel.exists():announce('interrupted',progress=0);return
    v=VTS(port);playing=False;unloaded=False;position=None;trace=[]
    try:
        v.authenticate();current=v.call('CurrentModelRequest')
        if not current.get('modelLoaded') or current.get('modelID')!=mid:
            load_model(v,mid);current=wait_model(v,mid)
        position=current['modelPosition']
        def changes_parameters(name):
            files=list(MODEL_ROOT.rglob(name))
            if len(files)!=1:return True
            ps=read_json(files[0]).get('Parameters',[])
            return any(not (p.get('Blend')=='Add' and p['Value']==0 or p.get('Blend')=='Multiply' and p['Value']==1) for p in ps)
        active=[x['file'] for x in v.call('ExpressionStateRequest')['expressions'] if x['active'] and changes_parameters(x['file'])]
        if active:raise ValueError('请先关闭 VTS 活跃表情，避免覆盖新动作：'+repr(active))
        announce('deploying',progress=0)
        load_model(v,'');unloaded=True;time.sleep(2.2)
        c=read_json(configfile);backup=folder/'vtube-before.json';backup.write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf-8')
        h=copy.deepcopy(next(x for x in c['Hotkeys'] if x['Action']=='TriggerAnimation'))
        h.update(HotkeyID=HOTKEY,Name='Jingyu Agent Live',File=motion.name,Folder='',StopsOnLastFrame=False,FadeSecondsAmount=0.0,DeactivateAfterKeyUp=False,DeactivateAfterSeconds=False,IsGlobal=False)
        h['Triggers']={'Trigger1':'','Trigger2':'','Trigger3':'','ScreenButton':-1}
        c['Hotkeys']=[x for x in c['Hotkeys'] if x['HotkeyID']!=HOTKEY]+[h]
        shutil.copy2(motion,dest/motion.name);tmp=configfile.with_suffix('.tmp');tmp.write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(configfile)
        load_model(v,mid);wait_model(v,mid);unloaded=False
        v.call('MoveModelRequest',{'timeInSeconds':0,'valuesAreRelativeToModel':False,**position})
        hs=v.call('HotkeysInCurrentModelRequest')['availableHotkeys']
        if not any(x['hotkeyID']==HOTKEY and x['file']==motion.name for x in hs):raise RuntimeError('VTS 未加载新动作热键')
        if cancel.exists():announce('interrupted',progress=0);return
        keep={'faceFound':True,'mode':'set','parameterValues':[{'id':'FaceAngleX','value':0,'weight':0}]}
        v.call('InjectParameterDataRequest',keep);v.call('HotkeyTriggerRequest',{'hotkeyID':HOTKEY});playing=True;t0=time.monotonic();duration=job['compiled']['duration'];announce('playing',progress=0,motion=motion.name)
        while time.monotonic()-t0<duration+1:
            if cancel.exists():
                announce('stopping',progress=min(1,(time.monotonic()-t0)/duration));reload_model(v,mid,position);playing=False;announce('interrupted',progress=0);return
            v.call('InjectParameterDataRequest',keep);r=v.call('Live2DParameterListRequest')
            if r.get('modelID')!=mid:raise RuntimeError('VTS 模型在播放期间被切换')
            values={x['name']:x['value'] for x in r['parameters']}
            if not all(math.isfinite(x) for x in values.values()):raise RuntimeError('VTS 参数出现非有限值')
            elapsed=time.monotonic()-t0;trace.append({'time':elapsed,'values':values});announce('playing',progress=min(.99,elapsed/duration),elapsed=elapsed,values={k:values[k] for k in ['AngleX','LeanInput','Movement2','Movement3','key7']})
            time.sleep(.2)
        playing=False
        # A full trace is retained; completion means playback interval + recovery sampled.
        announce('completed',progress=1,samples=len(trace),motion=motion.name)
    except BaseException:
        if position is not None:
            try:
                if unloaded:load_model(v,mid);wait_model(v,mid)
                elif playing:reload_model(v,mid,position)
            except Exception as e:announce('recovery-error',error=str(e))
        raise
    finally:
        (folder/'vts-trace.json').write_text(json.dumps({'jobId':job['id'],'samples':trace,'motion':motion.name,'sha256':hashlib.sha256(motion.read_bytes()).hexdigest()},ensure_ascii=False),encoding='utf-8');v.close()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('job');p.add_argument('--cancel',required=True);p.add_argument('--port',type=int,default=8001);a=p.parse_args()
    try:deploy(a.job,Path(a.cancel),a.port)
    except Exception as e:announce('error',error=str(e));raise SystemExit(1)
