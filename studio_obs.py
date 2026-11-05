"""OBS v5 control, isolated from the main server's optional dependencies."""
import base64, hashlib, json, os, sys, time
from pathlib import Path
import websocket
from model_profile import ROOT

def run(action, scene=None):
    if action not in ('status','switch','record','stop'):raise ValueError('不支持的 OBS 操作')
    path=ROOT/'.local/obs-experiment-password'
    password=os.environ.get('JINGYU_OBS_PASSWORD') or (path.read_text(encoding='utf-8-sig').strip() if path.exists() else '')
    ws=websocket.create_connection('ws://127.0.0.1:4455',timeout=5)
    try:
        hello=json.loads(ws.recv())['d']
        identity={'rpcVersion':1,'eventSubscriptions':0}
        if 'authentication' in hello:
            a=hello['authentication']
            secret=base64.b64encode(hashlib.sha256((password+a['salt']).encode()).digest()).decode()
            identity['authentication']=base64.b64encode(hashlib.sha256((secret+a['challenge']).encode()).digest()).decode()
        ws.send(json.dumps({'op':1,'d':identity}))
        if json.loads(ws.recv())['op']!=2:raise ValueError('OBS 认证失败')
        seq=0
        def call(kind,**params):
            nonlocal seq
            seq+=1;rid=str(seq)
            ws.send(json.dumps({'op':6,'d':{'requestId':rid,'requestType':kind,'requestData':params}}))
            while True:
                r=json.loads(ws.recv())
                if r['op']==7 and r['d']['requestId']==rid:
                    d=r['d']
                    if not d['requestStatus']['result']:raise ValueError('OBS '+kind+': '+str(d['requestStatus']))
                    return d.get('responseData',{})
        if action=='switch':
            scenes=call('GetSceneList')
            if scene not in [s['sceneName'] for s in scenes['scenes']]:raise ValueError('OBS 场景不存在')
            call('SetCurrentProgramScene',sceneName=scene)
            if call('GetSceneList')['currentProgramSceneName']!=scene:raise ValueError('场景切换未生效')
        elif action=='record':
            if call('GetRecordStatus')['outputActive']:raise ValueError('OBS 已经在录制')
            call('StartRecord')
            for _ in range(30):
                if call('GetRecordStatus')['outputActive']:break
                time.sleep(.1)
            else:raise ValueError('OBS 未进入录制状态，请检查首次配置对话框或录制设置')
        elif action=='stop':
            if not call('GetRecordStatus')['outputActive']:raise ValueError('OBS 当前未录制')
            result=call('StopRecord')
            return {'ok':True,**result}
        return {'ok':True,'recording':call('GetRecordStatus'),'scenes':call('GetSceneList')}
    finally:ws.close()

if __name__=='__main__':
    try:
        request=json.load(sys.stdin)
        print(json.dumps(run(request['action'],request.get('scene')),ensure_ascii=False))
    except Exception as e:
        print(json.dumps({'error':str(e)},ensure_ascii=False));sys.exit(1)
