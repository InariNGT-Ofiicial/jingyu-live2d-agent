"""Loopback VTS client. Correlated replies; tokens encrypted with Windows DPAPI."""
import argparse, ctypes, json, time, uuid, os
from pathlib import Path
import websocket

PLUGIN = {'pluginName':'Jingyu Motion Bridge','pluginDeveloper':'Jingyu Local Agent'}
TOKEN = Path(os.getenv('L2D_VTS_TOKEN_FILE') or Path(__file__).resolve().parent/'.local'/'vts-token.dpapi')

def protect(data, decrypt=False):
    class Blob(ctypes.Structure):
        _fields_=[('size',ctypes.c_ulong),('data',ctypes.POINTER(ctypes.c_char))]
    buf=ctypes.create_string_buffer(data);src=Blob(len(data),ctypes.cast(buf,ctypes.POINTER(ctypes.c_char)));out=Blob()
    fn=ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    if not fn(ctypes.byref(src),None,None,None,None,1,ctypes.byref(out)):
        raise ctypes.WinError()
    try:return ctypes.string_at(out.data,out.size)
    finally:ctypes.windll.kernel32.LocalFree(out.data)

class VTS:
    def __init__(self,port=8001,timeout=8):
        self.ws=websocket.create_connection(f'ws://127.0.0.1:{int(port)}',timeout=timeout,http_no_proxy=['127.0.0.1'])
    def close(self):self.ws.close()
    def call(self,kind,data=None,timeout=8):
        rid=uuid.uuid4().hex
        self.ws.send(json.dumps({'apiName':'VTubeStudioPublicAPI','apiVersion':'1.0','requestID':rid,'messageType':kind,'data':data or {}}))
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            self.ws.settimeout(max(.01,end-time.monotonic()))
            reply=json.loads(self.ws.recv())
            if reply.get('requestID')!=rid:continue
            if reply.get('messageType')=='APIError':raise RuntimeError(f"VTS API error {reply.get('data',{}).get('errorID')}: {reply.get('data',{}).get('message')}")
            if reply.get('messageType')!=kind.removesuffix('Request')+'Response':raise RuntimeError('Unexpected VTS response type')
            return reply['data']
        raise TimeoutError(kind)
    def authenticate(self):
        token=None
        if TOKEN.exists():token=protect(TOKEN.read_bytes(),True).decode()
        if token and self.call('AuthenticationRequest',{**PLUGIN,'authenticationToken':token}).get('authenticated'):return
        print('Awaiting VTS permission: Jingyu Motion Bridge',flush=True)
        token=self.call('AuthenticationTokenRequest',PLUGIN,timeout=60)['authenticationToken']
        if not self.call('AuthenticationRequest',{**PLUGIN,'authenticationToken':token}).get('authenticated'):raise RuntimeError('VTS authentication denied')
        TOKEN.parent.mkdir(parents=True,exist_ok=True);TOKEN.write_bytes(protect(token.encode()))
    def require_model(self,model_id):
        model=self.call('CurrentModelRequest')
        if not model.get('modelLoaded') or model.get('modelID')!=model_id:raise RuntimeError('VTS loaded model does not match comparison model')
        return model

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['state','inspect']);p.add_argument('--port',type=int,default=8001);p.add_argument('--output');a=p.parse_args()
    v=VTS(a.port)
    try:
        result={'api':v.call('APIStateRequest')}
        if a.command=='inspect':
            v.authenticate()
            for kind in ['StatisticsRequest','CurrentModelRequest','AvailableModelsRequest','HotkeysInCurrentModelRequest']:
                result[kind]=v.call(kind)
        if a.output:Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=True,indent=2))
    finally:v.close()
