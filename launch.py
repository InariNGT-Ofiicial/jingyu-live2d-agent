"""Portable local beta launcher, preferring the complete bundled model."""
import argparse,json,os,subprocess,sys,time,webbrowser
from pathlib import Path
from urllib.request import urlopen
from platform_support import no_window_flags, platform_name, capture_available
ROOT=Path(__file__).resolve().parent
def main():
 p=argparse.ArgumentParser();p.add_argument('--model-dir');p.add_argument('--port',type=int,default=61942);p.add_argument('--no-browser',action='store_true');p.add_argument('--check',action='store_true');a=p.parse_args()
 if not 1024<=a.port<=65535:p.error('port 必须在 1024..65535')
 saved=ROOT/'.local/model-path.txt'
 path=a.model_dir or os.getenv('L2D_MODEL_DIR') or (saved.read_text(encoding='utf-8').strip() if saved.is_file() else None)
 bundled=ROOT/'model'/'DeepSeek'
 model=Path(path) if path else bundled if bundled.is_dir() else ROOT.parent/'DeepSeek-L2D/DeepSeek免费公皮/DeepSeek'
 if not model.is_dir() and not a.check:
  path=input('请粘贴解压后的 DeepSeek 模型目录（含大肥鱼.model3.json）：').strip().strip('"');model=Path(path)
 required=['大肥鱼.model3.json','大肥鱼.cdi3.json','大肥鱼.physics3.json','Exp3','Animation']
 missing=[x for x in required if not (model/x).exists()]
 if missing:raise SystemExit('模型目录不完整：'+str(model)+'；缺少 '+', '.join(missing))
 os.environ['L2D_MODEL_DIR']=str(model.resolve());os.environ['PYTHONIOENCODING']='utf-8'
 # Validate referenced model assets before starting the HTTP server.
 sys.path.insert(0,str(ROOT))
 from model_profile import read_json, MODEL_ROOT
 refs=read_json(MODEL_ROOT/'大肥鱼.model3.json')['FileReferences']
 for rel in [refs['Moc'],*refs['Textures']]:
  if not (MODEL_ROOT/rel).is_file():raise SystemExit('缺少模型资产：'+rel)
 if a.check:
  print(json.dumps({'version':'1.4.0-beta.3','python':sys.version.split()[0],'modelReady':True,'platform':platform_name(),'nativeCapture':capture_available()},ensure_ascii=False));return
 saved.parent.mkdir(exist_ok=True);saved.write_text(str(model.resolve()),encoding='utf-8')
 url=f'http://127.0.0.1:{a.port}'
 try:
  with urlopen(url+'/api/state',timeout=2) as r:state=json.load(r)
 except OSError:state=None
 if state is not None:
  if state.get('version')!='1.4.0-beta.3':raise SystemExit('端口已有其他版本服务，请先关闭它或选择其他 --port')
 else:
  logs=ROOT/'logs';logs.mkdir(exist_ok=True)
  with (logs/'server.log').open('a',encoding='utf-8') as stdout,(logs/'server-error.log').open('a',encoding='utf-8') as stderr:
   process=subprocess.Popen([sys.executable,'-u',str(ROOT/'server.py'),'--port',str(a.port)],cwd=ROOT,stdout=stdout,stderr=stderr,creationflags=no_window_flags())
  (logs/'server.pid').write_text(str(process.pid))
  for _ in range(60):
   if process.poll() is not None:raise SystemExit('启动失败，请查看 logs/server-error.log')
   try:
    with urlopen(url+'/api/state',timeout=1) as r:json.load(r)
    break
   except OSError:time.sleep(.25)
  else:raise SystemExit('启动超时，请查看 logs/server-error.log')
 if not a.no_browser:webbrowser.open(url)
 print('鲸语 Beta 已就绪：'+url)
if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');main()
