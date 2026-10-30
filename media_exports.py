"""Bounded, sequential PNG ingestion and FFmpeg export jobs."""
import base64,json,math,re,struct,subprocess,threading,time,uuid
from pathlib import Path
from model_profile import ROOT
from runtime_tools import executable
class ExportManager:
    def __init__(self,emit,lock=None):
        # Share the server's reentrant state lock: emit() and command guards also
        # acquire it, so separate locks would invert order during native capture.
        self.emit=emit;self.lock=lock if lock is not None else threading.RLock();self.jobs={};self.procs={}
        self.scratch=ROOT/'.local'/'export-frames';self.output=ROOT/'exports'
    def native_busy(self):
        with self.lock:return any(j.get('nativeRunning') for j in self.jobs.values())
    def busy(self):
        with self.lock:return any(j.get('nativeRunning') or j['status'] in ['queued','rendering','recording','compiling','deploying','encoding','cancelling'] for j in self.jobs.values())
    def public(self,j):return {k:v for k,v in j.items() if k not in ['compiled','bytes','token','busy']}
    def get(self,jid):
        with self.lock:
            j=self.jobs.get(jid)
            if not j and isinstance(jid,str) and re.fullmatch('[0-9a-f]{12}',jid):
                manifest=self.output/jid/'manifest.json'
                if manifest.is_file():return json.loads(manifest.read_text(encoding='utf-8'))
            if not j:raise ValueError('导出任务不存在')
            if j['status'] in ['queued','rendering'] and time.time()-j['updated']>120:self.fail(jid,'渲染端 120 秒未响应，请重新导出')
            return self.public(j)
    def start(self,compiled,options,client):
        renderer=options.get('renderer','web')
        if renderer not in ['web','vts']:raise ValueError('导出 renderer 必须为 web 或 vts')
        sender=options.get('sender','')
        if not isinstance(sender,str) or len(sender)>256:raise ValueError('sender 必须是最多 256 字符的 Spout 名称')
        fmt=options.get('format','gif');w=options.get('width',512);h=options.get('height',768);fps=options.get('fps',15)
        if fmt not in ['gif','mp4']:raise ValueError('导出格式为 gif 或 mp4')
        if any(type(x)is not int for x in [w,h,fps]) or not 128<=w<=1280 or not 128<=h<=1280 or w%2 or h%2 or not 5<=fps<=30:raise ValueError('尺寸为 128..1280 偶数；帧率为 5..30 整数')
        if fmt=='mp4' and options.get('transparent') is True:raise ValueError('H.264 MP4 不支持透明底；请选择透明 GIF，或设置 MP4 背景色')
        background=options.get('background','#f5f7f5')
        if not isinstance(background,str) or not re.fullmatch('#[0-9a-fA-F]{6}',background):raise ValueError('背景色必须为 #RRGGBB')
        frames=math.ceil(compiled['duration']*fps)
        if w*h*frames>900_000_000:raise ValueError('本次导出像素总量过大，请降低尺寸或帧率')
        ffmpeg=executable('ffmpeg')
        check=subprocess.run([ffmpeg,'-hide_banner','-encoders'],capture_output=True,text=True,timeout=10,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        encoder='gif' if fmt=='gif' else 'libx264'
        if not re.search(r'\s'+encoder+r'\s',check.stdout):raise ValueError(f'当前 FFmpeg 缺少 {encoder} 编码器，请配置完整构建')
        with self.lock:
            for old in list(self.jobs):self.get(old)
            if self.busy():raise ValueError('已有导出正在进行，请等待完成或取消')
            jid=uuid.uuid4().hex[:12];j={'id':jid,'format':fmt,'width':w,'height':h,'fps':fps,'frameCount':frames,'duration':frames/fps,'planDuration':compiled['duration'],'background':background,'transparent':fmt=='gif','renderer':'web-cubism','clientId':client,'compiled':compiled,'token':uuid.uuid4().hex,'status':'queued','received':0,'bytes':0,'progress':0,'updated':time.time(),'createdAt':time.time()}
            self.jobs[jid]=j;(self.scratch/jid).mkdir(parents=True);(self.output/jid).mkdir(parents=True)
            if renderer=='vts':
                j.update(renderer='vts-spout2',clientId=None,sender=sender,nativeRunning=True)
                threading.Thread(target=self.record_native,args=(jid,),daemon=True).start()
                return self.public(j)
            self.emit('export',dict(j));return self.public(j)
    def record_native(self,jid):
        j=self.jobs[jid];folder=self.scratch/jid;cancel=folder/'cancel';captured=False;error=None;timer=None
        try:
            options={k:j[k] for k in ['format','width','height','fps','frameCount','sender']}
            jobfile=folder/'job.json';jobfile.write_text(json.dumps({'id':jid,'compiled':j['compiled'],'capture':options},ensure_ascii=False),encoding='utf-8')
            with (self.output/jid/'capture.log').open('w',encoding='utf-8') as log:
                p=subprocess.Popen([executable('capture_python'),'-u',str(ROOT/'vts_capture.py'),'--job',str(jobfile),'--cancel',str(cancel)],stdout=subprocess.PIPE,stderr=log,text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                self.procs[jid]=p
                def timeout():
                    cancel.touch()
                    if p.poll() is None:p.kill()
                timer=threading.Timer(j['duration']+180,timeout);timer.daemon=True;timer.start()
                for line in p.stdout:
                    log.write(line);log.flush()
                    try:event=json.loads(line)
                    except ValueError:continue
                    with self.lock:
                        if event.get('status')=='error':error=event.get('error')
                        if event.get('status')=='captured':
                            captured=event.get('received')==j['frameCount'];j['capture']=event.get('capture',{})
                        if j['status']!='cancelling' and event.get('status') in ['compiling','deploying','recording']:
                            j.update(status=event['status'],updated=time.time(),progress=event.get('progress',j['progress']),received=event.get('received',j['received']))
                            self.emit('export-status',self.public(j))
                code=p.wait()
            with self.lock:
                j['nativeRunning']=False
                if j['status']=='cancelling':
                    j.update(status='cancelled',updated=time.time());self.emit('export-status',self.public(j));return
                if code or not captured:raise RuntimeError(error or 'VTS 原生采集失败，请检查 capture.log 和 Spout 依赖')
                report=folder/'capture-report.json'
                if report.is_file():(self.output/jid/'capture-report.json').write_bytes(report.read_bytes())
                j.update(status='encoding',received=j['frameCount'],progress=.8,updated=time.time());self.emit('export-status',self.public(j))
            self.procs.pop(jid,None);self.encode(jid)
        except Exception as e:self.fail(jid,e)
        finally:
            if timer:timer.cancel()
            j['nativeRunning']=False;self.procs.pop(jid,None)
    def frame(self,data):
        jid=data.get('id')
        with self.lock:
            j=self.jobs.get(jid)
            if not j or data.get('token')!=j['token'] or data.get('clientId')!=j['clientId']:raise ValueError('导出会话不匹配')
            if j['renderer']!='web-cubism':raise ValueError('原生导出不接受网页帧')
            if j['status'] not in ['queued','rendering']:raise ValueError('导出任务已停止接收帧')
            if type(data.get('index'))is not int or data['index']!=j['received']:raise ValueError('帧序号必须连续，禁止重复或跳帧')
            if j['received']>=j['frameCount']:raise ValueError('超出计划帧数')
            png=base64.b64decode(data.get('png',''),validate=True)
            if len(png)<24 or png[:8]!=b'\x89PNG\r\n\x1a\n' or struct.unpack('>II',png[16:24])!=(j['width'],j['height']):raise ValueError('无效 PNG 或尺寸不符')
            if len(png)>8_000_000 or j['bytes']+len(png)>2_000_000_000:raise ValueError('导出缓存超出限制')
            (self.scratch/jid/f'{j["received"]:06d}.png').write_bytes(png)
            j.update(status='rendering',received=j['received']+1,bytes=j['bytes']+len(png),updated=time.time());j['progress']=j['received']/j['frameCount']*.8
            if j['received']==j['frameCount']:
                j['status']='encoding';threading.Thread(target=self.encode,args=(jid,),daemon=True).start()
            return {'ok':True,'received':j['received']}
    def fail(self,jid,error):
        with self.lock:
            j=self.jobs.get(jid)
            if j and j['status'] not in ['completed','cancelled','error']:
                j.update(status='error',error=str(error)[:500],updated=time.time());self.emit('export-status',self.public(j))
    def cancel(self,jid):
        with self.lock:
            j=self.jobs.get(jid)
            if not j:raise ValueError('导出任务不存在')
            if j['status'] not in ['completed','error','cancelled']:
                if j.get('nativeRunning'):
                    (self.scratch/jid/'cancel').touch();j.update(status='cancelling',updated=time.time());self.emit('export-status',self.public(j));return self.public(j)
                j.update(status='cancelled',updated=time.time());p=self.procs.get(jid)
                if p and p.poll() is None:p.terminate()
                self.emit('export-status',self.public(j))
            return self.public(j)
    def encode(self,jid):
        j=self.jobs[jid];folder=self.output/jid;dest=folder/f'animation.{j["format"]}';tmp=folder/f'encoding.{j["format"]}'
        cmd=[executable('ffmpeg'),'-hide_banner','-loglevel','error','-y','-framerate',str(j['fps']),'-i',str(self.scratch/jid/'%06d.png')]
        if j['format']=='gif':cmd+=['-filter_complex','[0:v]split[a][b];[a]palettegen=reserve_transparent=1:stats_mode=diff[p];[b][p]paletteuse=dither=sierra2_4a:alpha_threshold=128','-loop','0']
        else:cmd+=['-f','lavfi','-i',f'color=c={j["background"]}:s={j["width"]}x{j["height"]}:r={j["fps"]}','-filter_complex','[1:v][0:v]overlay=shortest=1:format=auto,format=yuv420p[v]','-map','[v]','-c:v','libx264','-preset','fast','-crf','18','-movflags','+faststart','-an']
        cmd+=['-frames:v',str(j['frameCount']),str(tmp)]
        try:
            with (folder/'encode.log').open('w',encoding='utf-8') as log:
                with self.lock:
                    if j['status']=='cancelled':return
                    p=subprocess.Popen(cmd,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));self.procs[jid]=p
                code=p.wait(timeout=300)
            with self.lock:
                if j['status']=='cancelled':return
                if code or not tmp.is_file() or tmp.stat().st_size==0:raise RuntimeError('FFmpeg 编码失败，请检查本任务 encode.log')
                tmp.replace(dest);j.update(status='completed',progress=1,file=dest.name,size=dest.stat().st_size,url=f'/exports/{jid}/{dest.name}',updated=time.time())
                (folder/'manifest.json').write_text(json.dumps(self.public(j),ensure_ascii=False,indent=2),encoding='utf-8')
                self.emit('export-status',self.public(j))
        except Exception as e:
            p=self.procs.get(jid)
            if p and p.poll() is None:p.kill();p.wait()
            self.fail(jid,e)
        finally:self.procs.pop(jid,None)
