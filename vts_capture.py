"""Receive native VTS Spout RGBA frames. No window capture or chroma key fallback.

Spout2 is a DirectX shared-texture transport, so this receiver only exists on
Windows. macOS has no equivalent API; the honest alternatives there are NDI or
OBS capture, which this project does not pretend to implement.
"""
import argparse,array,hashlib,json,sys,threading,time
from pathlib import Path
from platform_support import IS_WINDOWS, CAPTURE_UNAVAILABLE

def announce(status,**data):print(json.dumps({'status':status,**data},ensure_ascii=True),flush=True)

def require_spout():
    if not IS_WINDOWS:raise RuntimeError(CAPTURE_UNAVAILABLE)

def choose_sender(names,requested=''):
    if requested:
        if requested not in names:raise ValueError('指定的 Spout 发送器不存在：'+requested)
        return requested
    matches=[n for n in names if n.lower().replace(' ','').startswith('vtubestudio')]
    if len(matches)!=1:raise ValueError('请开启 VTS 的 Spout2；存在多个 VTS 窗口时请指定 sender 名称')
    return matches[0]

def fit_rgba(im,width,height):
    from PIL import Image
    ratio=max(im.width/width,im.height/height)
    size=(max(1,round(im.width/ratio)),max(1,round(im.height/ratio)))
    # Box-reduce large GPU frames first, then refine edges at near-output size.
    # Pillow preserves premultiplied alpha during reduction/resampling.
    factor=max(1,int(ratio/1.25))
    if factor>1:im=im.reduce(factor)
    image=im.resize(size,Image.Resampling.LANCZOS)
    canvas=Image.new('RGBA',(width,height),(0,0,0,0))
    canvas.paste(image,((width-image.width)//2,(height-image.height)//2))
    return canvas

class Receiver:
    def __init__(self,name=''):
        require_spout()
        try:import SpoutGL
        except ImportError as e:raise RuntimeError('原生采集需要 Windows Python 3.12 环境及 requirements-capture.txt；请配置 CAPTURE_PYTHON') from e
        self.sdk=SpoutGL;self.receiver=SpoutGL.SpoutReceiver();self.buffer=None;self.size=None
        self.name=choose_sender(self.receiver.getSenderList(),name)
        if not self.receiver.createOpenGL():raise RuntimeError('无法建立 Spout 接收用图形上下文')
        import ctypes
        gl=ctypes.windll.opengl32.glGetString;gl.restype=ctypes.c_char_p
        self.gpu=(gl(0x1F01) or b'unknown').decode('utf-8',errors='replace')
        self.receiver.setReceiverName(self.name)
    def close(self):self.receiver.releaseReceiver();self.receiver.closeOpenGL()
    def read(self,timeout=2,expected=None):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            ok=self.receiver.receiveImage(self.buffer,self.sdk.enums.GL_RGBA,False,0)
            size=(self.receiver.getSenderWidth(),self.receiver.getSenderHeight())
            if self.receiver.isUpdated() or (size!=self.size and all(size)):
                if expected and size!=expected:raise RuntimeError('VTS 输出尺寸在录制中改变，请保持窗口尺寸后重试')
                if not all(size) or size[0]*size[1]>16_777_216:raise RuntimeError('Spout 输出尺寸无效或超过 4096² 像素预算')
                self.size=size;self.buffer=array.array('B',[0])*(size[0]*size[1]*4);continue
            if ok and self.buffer is not None and self.receiver.isConnected():
                if expected and size!=expected:raise RuntimeError('VTS 输出尺寸改变')
                return bytes(self.buffer),size,int(self.receiver.getSenderFrame())
            time.sleep(.005)
        raise RuntimeError('VTS Spout 无可读帧；请保持 VTS 窗口可见，且 VTS 与采集 Python 使用同一 GPU（见 setup_capture_gpu.py）')

def probe(requested=''):
    require_spout()
    try:import SpoutGL
    except ImportError as e:raise RuntimeError('原生采集需要 Windows Python 3.12 环境及 requirements-capture.txt；请配置 CAPTURE_PYTHON') from e
    r=SpoutGL.SpoutReceiver()
    try:names=list(r.getSenderList())
    finally:r.releaseReceiver()
    name=choose_sender(names,requested);receiver=Receiver(name)
    try:
        for _ in range(3):raw,size,frame=receiver.read();time.sleep(.03)
        from PIL import Image
        alpha=Image.frombytes('RGBA',size,raw).getchannel('A').getextrema()
        return {'available':True,'sender':name,'senders':names,'width':size[0],'height':size[1],'alphaRange':list(alpha),'senderFrame':frame,'transport':'spout2','receiverGPU':receiver.gpu}
    finally:receiver.close()

class Recorder:
    def __init__(self,options,folder,cancel):
        self.options=options;self.folder=folder;self.cancel=cancel;self.stop=threading.Event();self.prepare_event=threading.Event();self.prepared=threading.Event();self.go=threading.Event();self.ready=threading.Event();self.done=threading.Event();self.error=None;self.result={}
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def wait(self,event,timeout):
        end=time.monotonic()+timeout
        while not event.wait(.05):
            if self.error:raise RuntimeError(self.error)
            if self.cancel.exists():raise RuntimeError('录制已取消')
            if time.monotonic()>end:raise RuntimeError('等待 Spout 录制器超时')
        if self.error:raise RuntimeError(self.error)
    def prepare(self):self.prepare_event.set();self.wait(self.prepared,12)
    def start(self,t0):self.t0=t0;self.go.set()
    def close(self):self.stop.set();self.thread.join(5)
    def run(self):
        receiver=None
        try:
            from PIL import Image
            receiver=Receiver(self.options.get('sender',''));receiver.read();self.ready.set()
            while not self.prepare_event.wait(.05):
                if self.stop.is_set() or self.cancel.exists():return
            # Drain the asynchronous readback buffers and let VTS finish its
            # model-appearance / camera restoration transition before triggering.
            settle_until=time.monotonic()+1.0;deadline=time.monotonic()+8
            while True:
                raw,size,frame=receiver.read();im=Image.frombytes('RGBA',size,raw);alpha=im.getchannel('A').getextrema()
                if alpha[1]>0 and time.monotonic()>=settle_until:break
                if time.monotonic()>deadline:raise RuntimeError('VTS 原生画面为空，请确认角色已加载且在画面内')
                time.sleep(.03)
            if self.options['format']=='gif' and alpha[0]!=0:raise RuntimeError('VTS 未输出透明背景：请选择 ColorPicker 背景并启用 Transparent in capture')
            source_size=size;self.prepared.set()
            while not self.go.wait(.005):
                if self.stop.is_set() or self.cancel.exists():return
            fps=self.options['fps'];count=self.options['frameCount'];last_frame=None;last_hash=None;last_change=time.monotonic();duplicates=0;late=0;hashes=set();timings=[];byte_count=0
            for i in range(count):
                delay=self.t0+i/fps-time.monotonic()
                if delay>0:self.stop.wait(delay)
                if self.stop.is_set() or self.cancel.exists():return
                raw,size,frame=receiver.read(expected=source_size)
                stamp=time.monotonic()-self.t0
                if stamp-i/fps>max(.25,2/fps):late+=1
                digest=hashlib.sha256(raw).digest()
                if digest==last_hash:duplicates+=1
                last_hash=digest
                if frame>0 and frame==last_frame:
                    if time.monotonic()-last_change>2:raise RuntimeError('VTS 原生帧流已冻结超过 2 秒，未将静帧标记为成功')
                else:last_change=time.monotonic()
                last_frame=frame;hashes.add(digest)
                im=Image.frombytes('RGBA',size,raw)
                frame_alpha=im.getchannel('A').getextrema()
                if self.options['format']=='gif' and frame_alpha[0]!=0:raise RuntimeError('录制期间 VTS 透明背景被关闭，请重新启用透明输出')
                canvas=fit_rgba(im,self.options['width'],self.options['height'])
                file=self.folder/f'{i:06d}.png';canvas.save(file,compress_level=1);byte_count+=file.stat().st_size
                if byte_count>2_000_000_000:raise RuntimeError('原生录制缓存超过 2 GB 上限')
                timings.append({'index':i,'time':round(stamp,5),'senderFrame':frame})
                if i%max(1,fps//2)==0:announce('recording',received=i+1,progress=(i+1)/count*.8)
            if late>max(2,count//10):raise RuntimeError('本机原生采集持续落后，建议降低帧率或 VTS 输出分辨率')
            if len(hashes)<2:raise RuntimeError('采集到的整段画面完全相同，请检查 VTS 是否被最小化或暂停渲染')
            self.result={'transport':'spout2','sender':receiver.name,'receiverGPU':receiver.gpu,'sourceWidth':source_size[0],'sourceHeight':source_size[1],'alphaRange':list(alpha),'frames':count,'uniqueFrames':len(hashes),'duplicateFrames':duplicates,'lateFrames':late,'senderFrameCounterAvailable':bool(last_frame),'sampling':'wall-clock; aspect-fit; original RGBA; no chroma key','samples':timings}
        except Exception as e:self.error=str(e);self.cancel.touch()
        finally:
            if receiver:receiver.close()
            self.done.set()

def capture(jobfile,cancel):
    from vts_deploy import deploy
    jobfile=Path(jobfile);job=json.loads(jobfile.read_text(encoding='utf-8'));options=job['capture'];cancel=Path(cancel)
    recorder=Recorder(options,jobfile.parent,cancel)
    try:
        recorder.wait(recorder.ready,10)
        deploy(jobfile,cancel,recorder=recorder)
        if recorder.error:raise RuntimeError(recorder.error)
        if cancel.exists():announce('cancelled');return
        recorder.wait(recorder.done,10)
        result=recorder.result
        if result.get('frames')!=options['frameCount']:raise RuntimeError('录制未完成预期帧数')
        (jobfile.parent/'capture-report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        announce('captured',received=result['frames'],capture={k:v for k,v in result.items() if k!='samples'})
    finally:recorder.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--probe',action='store_true');p.add_argument('--sender',default='');p.add_argument('--job');p.add_argument('--cancel');a=p.parse_args()
    try:
        if a.probe:print(json.dumps(probe(a.sender),ensure_ascii=True))
        else:capture(a.job,a.cancel)
    except Exception as e:
        announce('error',error=str(e));raise SystemExit(1)
