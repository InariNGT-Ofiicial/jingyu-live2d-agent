"""Create a new VTS comparison copy; preserve original assets/config except one hotkey."""
import argparse,copy,hashlib,json,shutil
from pathlib import Path
from compiler import compile_plan
from model_profile import MODEL_ROOT,ROOT,read_json

HOTKEY='cd32a096a3c441ddad1883ab455a7715'
MOTION='Jingyu-Flirt-15.motion3.json'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def prepare(destination):
    destination=Path(destination).resolve()
    if destination.exists():raise ValueError('Destination exists; refusing to overwrite a model')
    source=MODEL_ROOT.resolve()
    if destination==source or source in destination.parents:raise ValueError('Original model is read-only')
    motion=ROOT/'research'/'vts-comparison'/MOTION
    if not motion.is_file():raise ValueError('Export motion first')
    config=read_json(source/'大肥鱼.vtube.json')
    before=copy.deepcopy(config)
    h=copy.deepcopy(next(h for h in config['Hotkeys'] if h['Action']=='TriggerAnimation'))
    h.update(HotkeyID=HOTKEY,Name='Jingyu Flirt Comparison',File=MOTION,Folder='',StopsOnLastFrame=False,FadeSecondsAmount=0.0,DeactivateAfterKeyUp=False,DeactivateAfterSeconds=False,IsGlobal=False)
    h['Triggers']={'Trigger1':'','Trigger2':'','Trigger3':'','ScreenButton':-1}
    config['Hotkeys'].append(h)
    shutil.copytree(source,destination)
    shutil.copy2(motion,destination/MOTION)
    (destination/'大肥鱼.vtube.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    changed=[str(p.relative_to(source)) for p in source.rglob('*') if p.is_file() and digest(p)!=digest(destination/p.relative_to(source))]
    assert changed==['大肥鱼.vtube.json'],changed
    assert {k:v for k,v in before.items() if k!='Hotkeys'}=={k:v for k,v in config.items() if k!='Hotkeys'}
    manifest={'source':str(source),'destination':str(destination),'modelID':config['ModelID'],'hotkeyID':HOTKEY,'motion':MOTION,'changedOriginalFiles':changed,'configDelta':'one added one-shot animation hotkey only','sourceConfigSha256':digest(source/'大肥鱼.vtube.json'),'physicsSha256':digest(source/'大肥鱼.physics3.json'),'motionSha256':digest(motion),'filesVerified':len([p for p in source.rglob('*') if p.is_file()])}
    (ROOT/'research'/'vts-comparison'/'import-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return manifest
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--destination');a=p.parse_args()
    folder=ROOT/'research'/'vts-comparison';folder.mkdir(exist_ok=True,parents=True)
    if a.destination:print(json.dumps(prepare(a.destination),ensure_ascii=True,indent=2))
    else:
        plan=read_json(ROOT/'performances'/'15-flirt-layered.json')
        (folder/'compiled.json').write_text(json.dumps(compile_plan(plan),ensure_ascii=False),encoding='utf-8')
        print('Compiled canonical performance 15')
