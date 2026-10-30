"""Agent entrypoint. Plain JSON over loopback; no browser automation needed."""
import argparse,json,time,sys
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError

def request(base,path,data=None):
    req=Request(base+path,data=json.dumps(data,ensure_ascii=False).encode('utf-8') if data is not None else None,
                headers={'Content-Type':'application/json'})
    try:
        with urlopen(req,timeout=30) as r: return json.load(r)
    except HTTPError as e:
        raise SystemExit(e.read().decode('utf-8'))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['state','capabilities','inbox','execute','compile','demo','stop','resolve','vts-export','vts-status','vts-perform','vts-stream','backend','backends','export','export-status','export-cancel','planner-config','planner-state','plan','play-plan','cancel-plan'])
    p.add_argument('value',nargs='?'); p.add_argument('--request-id'); p.add_argument('--url',default='http://127.0.0.1:61942')
    p.add_argument('--output');p.add_argument('--port',type=int,default=8001)
    p.add_argument('--backend',choices=['web','vts']);p.add_argument('--format',choices=['gif','mp4'],default='gif')
    p.add_argument('--width',type=int,default=512);p.add_argument('--height',type=int,default=768);p.add_argument('--fps',type=int,default=15)
    p.add_argument('--background',default='#f5f7f5');p.add_argument('--transparent',action='store_true');p.add_argument('--wait',action='store_true');a=p.parse_args()
    if a.command=='planner-config':
        result=request(a.url,'/api/planner/config',json.loads(Path(a.value).read_text(encoding='utf-8-sig')) if a.value else None)
    elif a.command=='planner-state':result=request(a.url,'/api/planner/state')
    elif a.command=='plan':
        if not a.value:p.error('plan 需要自然语言表演要求')
        result=request(a.url,'/api/planner/run',{'prompt':a.value,**({'backend':a.backend} if a.backend else {})})
        if a.wait:
            tid=result['id'];deadline=time.monotonic()+330
            while result['status'] in ['queued','generating','repairing']:
                if time.monotonic()>deadline:raise SystemExit('编排等待超时，请使用 planner-state 查询')
                time.sleep(1);result=next(t for t in request(a.url,'/api/planner/state')['tasks'] if t['id']==tid)
    elif a.command in ['play-plan','cancel-plan']:
        result=request(a.url,'/api/planner/'+('execute' if a.command=='play-plan' else 'cancel'),{'taskId':a.value})
    elif a.command=='vts-status':
        from vts_client import VTS
        v=VTS(a.port)
        try:
            v.authenticate();result={'api':v.call('APIStateRequest'),'model':v.call('CurrentModelRequest')}
        finally:v.close()
    elif a.command=='vts-perform':
        if a.value!='15':p.error('当前已验收的 VTS 原生表演为 15；其他动作可先导出并验收，不能静默替换。')
        from run_vts_comparison import run
        run(a.port,a.output or str(Path(__file__).parent/'logs'/'vts-last-performance.json'))
        raise SystemExit(0)
    elif a.command=='vts-stream':
        if not a.value or not a.output:p.error('vts-stream 需要计划文件与 --output 采集路径')
        from vts_tracking import play
        result=play(json.loads(Path(a.value).read_text(encoding='utf-8-sig')),a.port)
        Path(a.output).write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
        result={k:v for k,v in result.items() if k!='samples'}
    elif a.command=='vts-export':
        from vts_adapter import export_calibration
        if not a.value or not a.output:p.error('vts-export 需要计划 JSON 路径与 --output 文件路径')
        result=export_calibration(json.loads(Path(a.value).read_text(encoding='utf-8-sig')))
        Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        result={k:v for k,v in result.items() if k!='frames'}
    elif a.command=='backend':
        if a.value not in ['web','vts']:p.error('backend 需要 web 或 vts')
        result=request(a.url,'/api/backend',{'backend':a.value})
    elif a.command=='export':
        payload={'format':a.format,'width':a.width,'height':a.height,'fps':a.fps,'background':a.background,'transparent':a.transparent}
        if a.value:payload['plan']=json.loads(Path(a.value).read_text(encoding='utf-8-sig'))
        result=request(a.url,'/api/export',payload)
        if a.wait:
            print(json.dumps({'id':result['id'],'status':result['status']}),file=sys.stderr,flush=True)
            while result['status'] not in ['completed','error','cancelled']:
                time.sleep(1);result=request(a.url,'/api/export?id='+result['id'])
    elif a.command=='export-status':result=request(a.url,'/api/export?id='+str(a.value or ''))
    elif a.command=='export-cancel':result=request(a.url,'/api/export/cancel',{'id':a.value})
    elif a.command in ['state','capabilities','inbox','backends']: result=request(a.url,'/api/'+a.command)
    elif a.command in ['compile','execute']:
        if not a.value: p.error('需要动作计划 JSON 文件路径')
        payload={'plan':json.loads(Path(a.value).read_text(encoding='utf-8-sig'))}
        if a.request_id: payload['requestId']=a.request_id
        if a.backend:payload['backend']=a.backend
        result=request(a.url,'/api/'+a.command,payload)
        if a.command=='execute' and a.wait:
            jid=result['id'];deadline=time.monotonic()+180
            print(json.dumps({'id':jid,'status':result['status']}),file=sys.stderr,flush=True)
            while result['status'] not in ['completed','error','interrupted']:
                if time.monotonic()>deadline:raise SystemExit('等待超时；请用 state 查询任务，必要时 stop。')
                time.sleep(1);result=next(j for j in request(a.url,'/api/state')['jobs'] if j['id']==jid)
    elif a.command=='demo': result=request(a.url,'/api/demo',{'name':a.value,**({'backend':a.backend} if a.backend else {})})
    elif a.command=='resolve': result=request(a.url,'/api/inbox/resolve',{'id':a.request_id,'reason':a.value})
    else: result=request(a.url,'/api/stop',{})
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if isinstance(result,dict) and result.get('status') in ['error','cancelled']:raise SystemExit(1)
