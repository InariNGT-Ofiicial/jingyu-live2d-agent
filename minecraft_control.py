"""Local process switch and HTTP transport for the optional Minecraft adapter."""
import json,os,subprocess,time
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from runtime_tools import executable

ROOT=Path(__file__).resolve().parent
URL='http://127.0.0.1:61946'
def call(route,data=None):
    req=Request(URL+route,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'})
    try:
        with urlopen(req,timeout=3) as r:return json.load(r)
    except HTTPError as e:raise ValueError(json.load(e).get('error','Minecraft 请求失败')) from None
def state():
    try:return {'running':True,**call('/state')}
    except (URLError,OSError):return {'running':False,'ready':False}
def command(data,port):
    action=data.get('action')
    if action=='start':
        world=data.get('world','demo')
        if world not in ('demo','survival'):raise ValueError('world 必须为 demo 或 survival')
        current=state()
        if current['running']:
            if current.get('mode','demo')!=world:raise ValueError('请先关闭当前世界，再启动另一种世界')
            return current
        if not (ROOT/'minecraft/node_modules/mineflayer').exists() or not (ROOT/'.local/minecraft/runtime.json').exists():
            raise ValueError('请先运行 tools/setup_minecraft.py 并在 minecraft 目录 npm install')
        logs=ROOT/'logs';logs.mkdir(exist_ok=True)
        with (logs/'minecraft.log').open('a',encoding='utf-8') as log:
            process=subprocess.Popen([executable('node'),str(ROOT/'minecraft/bridge.cjs')],cwd=ROOT,stdout=log,stderr=log,
                env={**os.environ,'JINGYU_STUDIO_URL':f'http://127.0.0.1:{port}','JINGYU_MINECRAFT_WORLD':world},creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        for _ in range(20):
            if process.poll() is not None:raise ValueError('Minecraft 接口启动失败，请查看 logs/minecraft.log')
            current=state()
            if current['running']:return current
            time.sleep(.1)
        raise ValueError('Minecraft 接口启动超时，请查看 logs/minecraft.log')
    if action=='shutdown':return call('/shutdown',{})
    return call('/action',data)
