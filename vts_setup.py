"""Create or reuse an intact author-model copy; no manual parameter mapping."""
import hashlib,json,os,re,shutil
from pathlib import Path
from model_profile import ROOT,MODEL_ROOT,read_json
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def find_vts():
 roots=[]
 if os.getenv('L2D_VTS_DIR'):roots.append(Path(os.environ['L2D_VTS_DIR']))
 steam=[Path(os.getenv('ProgramFiles(x86)','C:/Program Files (x86)'))/'Steam']
 try:
  import winreg
  with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam') as key:steam.insert(0,Path(winreg.QueryValueEx(key,'SteamPath')[0]))
 except (ImportError,OSError):pass
 libraries=list(steam)
 for folder in steam:
  vdf=folder/'steamapps/libraryfolders.vdf'
  if vdf.is_file():libraries += [Path(x.replace('\\\\','\\'))for x in re.findall(r'"path"\s+"([^"]+)"',vdf.read_text(encoding='utf-8',errors='replace'))]
 roots += [p/'steamapps/common/VTube Studio' for p in libraries]
 for p in roots:
  if (p/'VTube Studio_Data/StreamingAssets/Live2DModels').is_dir():return p
 raise ValueError('未找到 VTube Studio；请安装或设置 L2D_VTS_DIR 为其安装目录')
def ensure_import():
 manifest=ROOT/'research/vts-comparison/import-manifest.json'
 if manifest.is_file():
  old=read_json(manifest)
  if Path(old.get('destination','')).is_dir():return old
 dest=find_vts()/'VTube Studio_Data/StreamingAssets/Live2DModels/Jingyu-Author-Comparison'
 mid=read_json(MODEL_ROOT/'大肥鱼.vtube.json')['ModelID']
 if dest.exists():
  if not (dest/'大肥鱼.vtube.json').is_file() or read_json(dest/'大肥鱼.vtube.json')['ModelID']!=mid or sha(dest/'大肥鱼.moc3')!=sha(MODEL_ROOT/'大肥鱼.moc3') or sha(dest/'大肥鱼.physics3.json')!=sha(MODEL_ROOT/'大肥鱼.physics3.json'):
   raise ValueError('VTS 专用目录已有不同模型，未覆盖；请改名后重新初始化')
 else:
  if dest.resolve()==MODEL_ROOT.resolve() or MODEL_ROOT.resolve() in dest.resolve().parents:raise ValueError('不能写入原模型目录')
  shutil.copytree(MODEL_ROOT,dest)
 result={'source':str(MODEL_ROOT),'destination':str(dest),'modelID':mid,'sourceConfigSha256':sha(MODEL_ROOT/'大肥鱼.vtube.json'),'physicsSha256':sha(MODEL_ROOT/'大肥鱼.physics3.json'),'method':'reuse matching copy or copy complete author model; native hotkey installed on first execution'}
 manifest.parent.mkdir(parents=True,exist_ok=True);manifest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');return result
if __name__=='__main__':print(json.dumps(ensure_import(),ensure_ascii=True,indent=2))
