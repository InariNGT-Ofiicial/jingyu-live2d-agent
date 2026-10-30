"""Loopback-only, dependency-free HTTP / SSE bridge for the current Codex agent."""
import argparse
from collections import deque
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json
import mimetypes
from pathlib import Path
import threading
import time
import uuid
import subprocess
from copy import deepcopy
from urllib.parse import urlsplit, unquote, parse_qs
from compiler import compile_plan, CompileError
from model_profile import ROOT, MODEL_ROOT, capabilities, write_profile
from demos import DEMOS
from runtime_tools import executable
from media_exports import ExportManager
from planner import Planner, PlannerError
from presets import PresetStore

LOCK=threading.Condition()
EVENTS=deque(maxlen=300); JOBS=deque(maxlen=40); INBOX=deque(maxlen=50)
CLIENTS={}; SEQ=0; ACTIVE=None
LAB=None
START=time.time()
BACKEND='web'
BUSY={'queued','compiling','deploying','playing','stopping'}
VTS_CANCEL={}
VERSION='1.4.0-beta.2'
PLANNER=Planner(ROOT/'.local'/'planner-settings.json')
PLANS=deque(maxlen=30)
PRESETS=PresetStore(ROOT/'.local'/'presets.json')

def planning_state():
    with LOCK:return deepcopy({'config':PLANNER.public(),'tasks':list(PLANS)})

def start_planning(prompt,backend=None):
    if not isinstance(prompt,str) or not 1<=len(prompt.strip())<=2000:raise PlannerError('请输入 1..2000 字的动作要求')
    with LOCK:
        backend=backend or BACKEND
        if backend not in ['web','vts']:raise PlannerError('无效执行后端')
        if any(t.get('running') for t in PLANS):raise PlannerError('已有编排请求尚未结束，请等待完成')
        if not PLANNER.public()['ready']:raise PlannerError('请先配置编排模型')
        task={'id':uuid.uuid4().hex[:12],'prompt':prompt.strip(),'backend':backend,'status':'queued','running':True,'createdAt':now()}
        PLANS.appendleft(task);snapshot=deepcopy(task)
    def worker():
        def update(phase):
            with LOCK:
                if task['status']!='cancelled':task['status']=phase;emit('planner',deepcopy(task))
        try:
            result=PLANNER.plan(prompt,update)
            with LOCK:
                if task['status']!='cancelled':task.update(status='validated',finishedAt=now(),**result)
        except Exception as error:
            with LOCK:
                if task['status']!='cancelled':task.update(status='error',error=str(error) if isinstance(error,(PlannerError,CompileError)) else '编排失败，请检查接口配置',finishedAt=now())
        finally:
            with LOCK:task['running']=False;emit('planner',deepcopy(task))
            folder=ROOT/'logs'/'planner';folder.mkdir(parents=True,exist_ok=True)
            (folder/(task['id']+'.json')).write_text(json.dumps(task,ensure_ascii=False,indent=2),encoding='utf-8')
    threading.Thread(target=worker,daemon=True).start();return snapshot

def now(): return datetime.now(timezone.utc).isoformat()
def reject_constant(value): raise CompileError(f'JSON 不允许非有限数字 {value}')
def expire_lab():
    if LAB and LAB['status'] in ['queued','running']:
        seen=CLIENTS.get(LAB['clientId'],{}).get('seen',0)
        if time.time()-max(seen,LAB.get('updatedEpoch',0))>30:
            LAB.update(status='failed',phase='舞台连接丢失，测试已释放',finishedAt=now())
            folder=ROOT/'stress';folder.mkdir(exist_ok=True)
            (folder/f'browser-{LAB["id"]}.json').write_text(json.dumps({'run':LAB,'result':{'summary':{'errors':1},'errors':[{'message':'renderer connection lost'}]}},ensure_ascii=False,indent=2),encoding='utf-8')
def emit(kind,data):
    global SEQ
    with LOCK:
        SEQ+=1; EVENTS.append({'id':SEQ,'event':kind,'data':data}); LOCK.notify_all()
        return SEQ
def state():
    with LOCK:
        expire_lab()
        live=[{'id':k,**v} for k,v in CLIENTS.items() if time.time()-v['seen']<8]
        return deepcopy({'bridge':'online','version':VERSION,'seq':SEQ,'uptime':round(time.time()-START), 'clients':live,
                'rendererReady':any(c.get('ready') for c in live),'backend':BACKEND,'activeJob':ACTIVE,
                'jobs':list(JOBS),'inbox':list(INBOX)})
def execute(plan,source='Codex',request_id=None,backend=None):
    global ACTIVE
    compiled=compile_plan(plan)
    with LOCK:
        if EXPORTS.native_busy():raise CompileError('VTS 原生录制中，请先取消录制或等待完成')
        expire_lab()
        if LAB and LAB['status'] in ['queued','running']: raise CompileError('压力测试正在运行，请先停止测试再执行动作')
        request=next((x for x in INBOX if x['id']==request_id),None) if request_id else None
        backend=backend or (request.get('backend') if request else None) or BACKEND
        if backend not in ['web','vts']:raise CompileError('后端必须为 web 或 vts')
        if request_id and request is None: raise CompileError('指令箱中没有这个 requestId')
        if request and request['status']!='pending': raise CompileError('此指令已处理；不重复执行')
        if ACTIVE and ACTIVE['status'] in BUSY:raise CompileError('已有动作正在执行，请先停止或等待完成')
        job={'id':uuid.uuid4().hex[:12],'source':source,'createdAt':now(),'status':'queued',
             'compiled':compiled,'requestId':request_id,'backend':backend,'progress':0,'reports':{}}
        JOBS.appendleft(job); ACTIVE=job
        if request:
            request.update(status='compiled',jobId=job['id'])
            emit('inbox',request)
        emit('execute',job)
        if backend=='vts':threading.Thread(target=run_vts_job,args=(job,),daemon=True).start()
        return job

def run_vts_job(job):
    folder=ROOT/'logs'/'vts-jobs'/job['id'];folder.mkdir(parents=True,exist_ok=True)
    file=folder/'job.json';file.write_text(json.dumps(job,ensure_ascii=False),encoding='utf-8')
    cancel=folder/'cancel';VTS_CANCEL[job['id']]=cancel
    if job['status']=='stopping':cancel.touch()
    try:
        with (folder/'worker.log').open('w',encoding='utf-8') as log:
            p=subprocess.Popen([executable('python'),'-u',str(ROOT/'vts_deploy.py'),str(file),'--cancel',str(cancel)],stdout=subprocess.PIPE,stderr=log,text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            for line in p.stdout:
                try:event=json.loads(line)
                except ValueError:continue
                status=event.get('status')
                if status not in BUSY|{'completed','interrupted','error','recovery-error'}:continue
                with LOCK:
                    if status=='recovery-error':job['recoveryError']=event.get('error');continue
                    job.update(status=status,progress=event.get('progress',job['progress']))
                    if 'error' in event:job['error']=event['error']
                    job['vts']=event
                    if status in ['completed','interrupted','error']:job['finishedAt']=now()
                    emit('backend-job',deepcopy(job))
            code=p.wait()
            if code or job['status'] not in ['completed','interrupted','error']:
                with LOCK:job.update(status='error',error=job.get('error','VTS 工作进程异常结束'),finishedAt=now());emit('backend-job',deepcopy(job))
    except Exception as e:
        with LOCK:job.update(status='error',error=str(e),finishedAt=now());emit('backend-job',deepcopy(job))
    finally:
        VTS_CANCEL.pop(job['id'],None);(folder/'result.json').write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf-8')

EXPORTS=ExportManager(emit,lock=LOCK)

class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*args): pass
    def handle(self):
        try: super().handle()
        except (ConnectionResetError,ConnectionAbortedError,BrokenPipeError): pass
    def json(self,data,status=200):
        body=json.dumps(data,ensure_ascii=False,allow_nan=False).encode('utf-8')
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(body)))
        self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(body)
    def valid_host(self):
        return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
    def do_GET(self):
        if not self.valid_host(): return self.json({'error':'仅允许本机访问'},403)
        parsed=urlsplit(self.path); route=unquote(parsed.path)
        if route=='/api/state': return self.json(state())
        if route=='/api/presets':
            try:return self.json({'presets':PRESETS.list()})
            except CompileError as e:return self.json({'error':str(e)},400)
        if route=='/api/planner/config':return self.json(PLANNER.public())
        if route=='/api/planner/state':return self.json(planning_state())
        if route=='/api/export/capabilities':
            try:
                p=subprocess.run([executable('capture_python'),str(ROOT/'vts_capture.py'),'--probe'],capture_output=True,text=True,encoding='utf-8',timeout=12,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                rows=[json.loads(line) for line in p.stdout.splitlines() if line.startswith('{')]
                native=rows[-1] if rows else {'available':False,'error':'原生录制依赖未安装，请查看 requirements-capture.txt'}
                if p.returncode:native['available']=False
            except Exception as e:native={'available':False,'error':str(e)}
            return self.json({'web':{'available':True},'vts':native})
        if route=='/api/export':
            try:return self.json(EXPORTS.get(parse_qs(parsed.query).get('id',[''])[0]))
            except ValueError as e:return self.json({'error':str(e)},404)
        if route=='/api/backends':
            vts={'available':False}
            try:
                r=subprocess.run([executable('python'),str(ROOT/'vts_client.py'),'state'],capture_output=True,text=True,encoding='utf-8',timeout=10)
                if r.returncode==0:vts={'available':True,**json.loads(r.stdout)}
                else:vts['error']='VTS 未运行或未开启插件 API'
            except Exception as e:vts['error']=str(e)
            return self.json({'selected':BACKEND,'web':{'available':True},'vts':vts})
        if route=='/api/capabilities': return self.json(capabilities())
        if route=='/api/demos': return self.json(DEMOS)
        if route=='/api/inbox': return self.json({'requests':list(INBOX)})
        if route=='/api/lab':
            with LOCK:
                expire_lab();value=deepcopy(LAB)
            return self.json({'run':value})
        if route=='/api/lab/result':
            rid=parse_qs(parsed.query).get('id',[''])[0]
            if not rid or any(c not in '0123456789abcdef' for c in rid) or len(rid)!=12: return self.json({'error':'无效测试编号'},400)
            file=ROOT/'stress'/f'browser-{rid}.json'
            if not file.exists(): return self.json({'error':'测试结果尚未生成'},404)
            return self.json(json.loads(file.read_text(encoding='utf-8')))
        if route=='/api/events':
            try: after=int(self.headers.get('Last-Event-ID') or parse_qs(parsed.query).get('after',['0'])[0])
            except ValueError: return self.json({'error':'无效事件序号'},400)
            if after>SEQ: after=0  # A restarted bridge starts a new event sequence.
            self.send_response(200); self.send_header('Content-Type','text/event-stream; charset=utf-8')
            self.send_header('Cache-Control','no-cache'); self.send_header('Connection','keep-alive'); self.end_headers()
            try:
                while True:
                    with LOCK:
                        pending=[e for e in EVENTS if e['id']>after]
                        if not pending: LOCK.wait(10); pending=[e for e in EVENTS if e['id']>after]
                    if not pending: self.wfile.write(b': heartbeat\n\n'); self.wfile.flush(); continue
                    for e in pending:
                        msg=f'id: {e["id"]}\nevent: {e["event"]}\ndata: {json.dumps(e["data"],ensure_ascii=False)}\n\n'
                        self.wfile.write(msg.encode('utf-8')); after=e['id']
                    self.wfile.flush()
            except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError): return
        if route.startswith('/api/'): return self.json({'error':'未知接口'},404)
        base=MODEL_ROOT if route.startswith('/model/') else ROOT/'exports' if route.startswith('/exports/') else ROOT/'web'
        rel=route[len('/model/'):] if route.startswith('/model/') else route[len('/exports/'):] if route.startswith('/exports/') else route.lstrip('/') or 'index.html'
        if route.startswith('/exports/') and (len(rel.split('/'))!=2 or rel.split('/')[-1] not in ['animation.gif','animation.mp4','manifest.json']):return self.json({'error':'导出文件不存在'},404)
        target=(base/rel).resolve()
        if not target.is_relative_to(base.resolve()) or not target.is_file(): return self.json({'error':'文件不存在'},404)
        data=target.read_bytes(); content_type=mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
        self.send_response(200); self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(data))); self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Cache-Control','public, max-age=3600' if route.startswith('/model/') or '/vendor/' in route else 'no-cache')
        self.end_headers(); self.wfile.write(data)
    def do_POST(self):
        global ACTIVE, LAB, BACKEND
        if not self.valid_host(): return self.json({'error':'仅允许本机访问'},403)
        origin=self.headers.get('Origin')
        if origin and origin not in {f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}:
            return self.json({'error':'拒绝跨站请求'},403)
        if self.headers.get('Content-Type','').split(';')[0]!='application/json': return self.json({'error':'需要 JSON'},415)
        try:
            length=int(self.headers.get('Content-Length','0'))
            limit=12_000_000 if urlsplit(self.path).path=='/api/export/frame' else 2097152 if urlsplit(self.path).path=='/api/lab/report' else 262144
            if not 0<length<=limit: return self.json({'error':'请求为空或过大'},413)
            data=json.loads(self.rfile.read(length),parse_constant=reject_constant)
            if not isinstance(data,dict): raise CompileError('请求必须是 JSON 对象')
            route=urlsplit(self.path).path
            if route=='/api/presets/save':return self.json(PRESETS.save(data.get('name'),data.get('plan')),201)
            if route=='/api/presets/delete':return self.json(PRESETS.delete(data.get('id')))
            if route=='/api/presets/play':
                preset=PRESETS.get(data.get('id'))
                return self.json(execute(preset['plan'],'我的预设 · '+preset['name'],backend=data.get('backend')),201)
            if route=='/api/replay':
                with LOCK:
                    job=next((x for x in JOBS if x['id']==data.get('jobId')),None)
                    if not job:raise CompileError('未找到要重播的动作')
                    return self.json(execute(job['compiled']['sourcePlan'],job['source'],backend=data.get('backend') or job['backend']),201)
            if route=='/api/planner/replay':
                with LOCK:
                    task=next((t for t in PLANS if t['id']==data.get('taskId')),None)
                    if not task or task['status']!='executed':raise PlannerError('该计划尚未执行，请先播放已校验计划')
                    job=execute(task['plan'],'LLM · '+task['planner']['model'],backend=data.get('backend') or task['backend'])
                    task['jobId']=job['id'];emit('planner',deepcopy(task));return self.json(job,201)
            if route=='/api/planner/config':
                with LOCK:
                    if any(t.get('running') for t in PLANS):raise PlannerError('编排请求结束后再修改配置')
                    return self.json(PLANNER.configure(data))
            if route=='/api/planner/run':return self.json(start_planning(data.get('prompt'),data.get('backend')),202)
            if route=='/api/planner/cancel':
                with LOCK:
                    task=next((t for t in PLANS if t['id']==data.get('taskId')),None)
                    if not task:raise PlannerError('未找到编排任务')
                    if task['status'] in ['queued','generating','repairing','validated']:task.update(status='cancelled',finishedAt=now());emit('planner',deepcopy(task))
                    return self.json(deepcopy(task))
            if route=='/api/planner/execute':
                with LOCK:
                    task=next((t for t in PLANS if t['id']==data.get('taskId')),None)
                    if not task or task['status']!='validated':raise PlannerError('请先生成并校验动作计划；同一计划不可重复提交')
                    job=execute(task['plan'],'LLM · '+task['planner']['model'],backend=task['backend'])
                    task.update(status='executed',jobId=job['id']);emit('planner',deepcopy(task));return self.json(job,201)
            if route=='/api/backend':
                if data.get('backend') not in ['web','vts']:raise CompileError('后端必须为 web 或 vts')
                with LOCK:
                    if EXPORTS.native_busy():raise CompileError('请等待 VTS 原生录制结束再切换后端')
                    if ACTIVE and ACTIVE['status'] in BUSY:raise CompileError('请先停止当前动作再切换后端')
                    BACKEND=data['backend'];emit('backend',{'backend':BACKEND})
                return self.json({'backend':BACKEND})
            if route=='/api/export':
                plan=data.get('plan') or (ACTIVE['compiled']['sourcePlan'] if ACTIVE else None)
                if not plan:raise CompileError('请先选择或编译一个动作计划')
                compiled=compile_plan(plan)
                if data.get('renderer','web')=='vts':
                    with LOCK:
                        if ACTIVE and ACTIVE['status'] in BUSY:raise CompileError('请先停止当前动作或等待完成，再录制完整 VTS 表演')
                        if LAB and LAB['status'] in ['queued','running']:raise CompileError('请先结束压力测试')
                        return self.json(EXPORTS.start(compiled,data,None),201)
                candidates=[k for k,v in CLIENTS.items() if v.get('ready') and v.get('telemetry',{}).get('exportReady') and time.time()-v['seen']<8]
                cid=data.get('clientId') or (candidates[0] if candidates else None)
                if cid not in candidates:raise CompileError('请打开新版网页舞台，等待导出渲染器就绪')
                return self.json(EXPORTS.start(compiled,data,cid),201)
            if route=='/api/export/frame':return self.json(EXPORTS.frame(data))
            if route=='/api/export/cancel':return self.json(EXPORTS.cancel(data.get('id')))
            if route=='/api/export/error':
                j=EXPORTS.jobs.get(data.get('id'))
                if not j or data.get('token')!=j['token'] or data.get('clientId')!=j['clientId']:raise CompileError('导出会话不匹配')
                EXPORTS.fail(j['id'],data.get('error','渲染失败'));return self.json({'ok':True})
            if route=='/api/lab/start':
                rounds=data.get('rounds',3)
                if type(rounds) is not int or not 1<=rounds<=3: raise CompileError('测试轮数必须为 1..3')
                with LOCK:
                    if EXPORTS.native_busy():raise CompileError('VTS 原生录制中，暂不能运行压力测试')
                    expire_lab()
                    if LAB and LAB['status'] in ['queued','running']: raise CompileError('已有压力测试在运行')
                    if ACTIVE and ACTIVE.get('backend')=='vts' and ACTIVE['status'] in BUSY:raise CompileError('请先停止 VTS 动作再开始压力测试')
                    candidates=[k for k,v in CLIENTS.items() if v.get('ready') and time.time()-v['seen']<8]
                    cid=data.get('clientId') or (candidates[0] if candidates else None)
                    if cid not in candidates: raise CompileError('请打开并激活实时舞台，等待模型就绪')
                    if ACTIVE and ACTIVE['status'] in ['queued','playing']: ACTIVE.update(status='interrupted',finishedAt=now())
                    emit('stop',{'reason':'进入隔离压力测试'})
                    LAB={'id':uuid.uuid4().hex[:12],'clientId':cid,'rounds':rounds,'status':'queued','createdAt':now(),'updatedEpoch':time.time(),'progress':0,'phase':'等待舞台'}
                    emit('lab',LAB)
                    return self.json(deepcopy(LAB),201)
            if route=='/api/lab/report':
                with LOCK:
                    if not LAB or data.get('id')!=LAB['id'] or data.get('clientId')!=LAB['clientId']: raise CompileError('测试会话不匹配')
                    if data.get('status') not in ['running','completed','failed','cancelled']: raise CompileError('无效测试状态')
                    if LAB['status'] not in ['queued','running']: return self.json({'ok':True,'ignored':True})
                    progress=data.get('progress',0)
                    if not isinstance(progress,(int,float)) or isinstance(progress,bool) or not 0<=progress<=1: raise CompileError('无效进度')
                    LAB.update(status=data['status'],progress=progress,phase=str(data.get('phase',''))[:120],updatedEpoch=time.time())
                    if data['status'] in ['completed','failed','cancelled']:
                        LAB['finishedAt']=now()
                        result=data.get('result',{})
                        LAB['summary']=result.get('summary',{})
                        (ROOT/'stress').mkdir(exist_ok=True)
                        (ROOT/'stress'/f'browser-{LAB["id"]}.json').write_text(json.dumps({'run':LAB,'result':result},ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
                return self.json({'ok':True})
            if route=='/api/compile': return self.json(compile_plan(data.get('plan',data)))
            if route=='/api/execute': return self.json(execute(data.get('plan',data),'Codex',data.get('requestId'),data.get('backend')),201)
            if route=='/api/demo':
                if data.get('name') not in DEMOS: raise CompileError('不存在这个动作示例')
                return self.json(execute(DEMOS[data['name']],'动作示例',backend=data.get('backend')),201)
            if route=='/api/inbox':
                prompt=data.get('prompt')
                if not isinstance(prompt,str) or not 1<=len(prompt.strip())<=2000: raise CompileError('请输入 1..2000 字的动作要求')
                with LOCK:
                    if sum(x['status']=='pending' for x in INBOX)>=12: raise CompileError('指令箱已满，请先让 Codex 处理已有指令')
                    backend=data.get('backend',BACKEND)
                    if backend not in ['web','vts']:raise CompileError('无效后端')
                    item={'id':uuid.uuid4().hex[:10],'prompt':prompt.strip(),'backend':backend,'status':'pending','createdAt':now()}
                    INBOX.appendleft(item); emit('inbox',item)
                return self.json(item,201)
            if route=='/api/inbox/resolve':
                with LOCK:
                    request=next((x for x in INBOX if x['id']==data.get('id')),None)
                    if request is None: raise CompileError('未找到这条指令')
                    if request['status']!='pending': raise CompileError('此指令已处理，不能更改结果')
                    request.update(status='declined',reason=str(data.get('reason','模型不支持该动作'))[:1000])
                    emit('inbox',request); return self.json(request)
            if route=='/api/stop':
                with LOCK:
                    for jid,j in list(EXPORTS.jobs.items()):
                        if j.get('nativeRunning'):EXPORTS.cancel(jid)
                    if ACTIVE and ACTIVE['status'] in BUSY:
                        if ACTIVE.get('backend')=='vts':
                            ACTIVE['status']='stopping';path=VTS_CANCEL.get(ACTIVE['id'])
                            if path:path.touch()
                        else:ACTIVE.update(status='interrupted',finishedAt=now())
                    emit('stop',{'reason':'用户停止','returnToIdle':True})
                return self.json({'ok':True})
            if route=='/api/heartbeat':
                cid=str(data.get('clientId',''))[:80]
                if not cid: raise CompileError('缺少 clientId')
                with LOCK:
                    CLIENTS[cid]={'seen':time.time(),'ready':data.get('ready') is True,'telemetry':data.get('telemetry',{})}
                    if len(CLIENTS)>20:
                        for k in list(CLIENTS):
                            if time.time()-CLIENTS[k]['seen']>60: del CLIENTS[k]
                return self.json({'ok':True,'seq':SEQ})
            if route=='/api/report':
                with LOCK:
                    job=next((j for j in JOBS if j['id']==data.get('jobId')),None)
                    status=data.get('status')
                    if job is None: raise CompileError('未知 jobId')
                    if job.get('backend')=='vts':raise CompileError('网页不能回报 VTS 作业状态')
                    if status not in ['playing','completed','error']: raise CompileError('无效回执状态')
                    cid=str(data.get('clientId',''))[:80]
                    progress=data.get('progress',0)
                    if isinstance(progress,bool) or not isinstance(progress,(int,float)) or not 0<=progress<=1: raise CompileError('无效进度')
                    report={'status':status,'progress':progress,'at':now(),'error':str(data.get('error',''))[:500]}
                    previous=job['reports'].get(cid)
                    if not previous or previous['status']=='playing': job['reports'][cid]=report
                    if job['status'] in ['queued','playing']:
                        job.update(status=status,progress=progress)
                        if status in ['completed','error']: job['finishedAt']=now()
                return self.json({'ok':True})
            return self.json({'error':'未知接口'},404)
        except (CompileError,ValueError,KeyError,TypeError) as e: return self.json({'error':str(e)},400)
        except Exception as e:
            print('SERVER ERROR',repr(e),flush=True)
            return self.json({'error':'本地桥接服务发生错误，请查看终端'},500)

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--port',type=int,default=61942); args=p.parse_args()
    write_profile()
    from build_stress_catalog import build
    build()
    previous=sorted((ROOT/'stress').glob('browser-*.json'),key=lambda p:p.stat().st_mtime)
    if previous:
        try: LAB=json.loads(previous[-1].read_text(encoding='utf-8'))['run']
        except (ValueError,KeyError): pass
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler); server.daemon_threads=True
    print(f'鲸语 · L2D Agent Bridge http://127.0.0.1:{args.port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: server.server_close()
