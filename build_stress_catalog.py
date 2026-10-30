"""Build a model-specific stress catalog without modifying received assets."""
import sys,json,hashlib,struct
from pathlib import Path
from model_profile import ROOT,MODEL_ROOT,PARAMS,PRIMARY,EXPRESSIONS,MOTIONS,PHYSICS,read_json

def build():
    inputs={i['Source']['Id'] for r in PHYSICS['PhysicsSettings'] for i in r['Input']}
    outputs={o['Destination']['Id'] for r in PHYSICS['PhysicsSettings'] for o in r['Output']}
    expids={p['Id'] for e in EXPRESSIONS.values() for p in e['Parameters']}
    motionids={c['Id'] for m in MOTIONS.values() for c in m['Curves'] if c['Target']=='Parameter'}
    model=read_json(MODEL_ROOT/'大肥鱼.model3.json');vts=read_json(MODEL_ROOT/'大肥鱼.vtube.json')
    mapping=[{k:v for k,v in p.items() if k in ['Name','Input','InputRangeLower','InputRangeUpper','OutputLive2D','OutputRangeLower','OutputRangeUpper','ClampInput','ClampOutput','Smoothing','UseBlinking','UseBreathing']} for p in vts['ParameterSettings']]
    hotkeys=[]
    files={p.name for p in MODEL_ROOT.rglob('*') if p.is_file()}
    for h in vts['Hotkeys']:
        hotkeys.append({k:h[k] for k in ['Name','Action','File','IsActive','StopsOnLastFrame'] if k in h})
        hotkeys[-1]['fileExists']=not h.get('File') or h['File'] in files
    textures=[]
    for rel in model['FileReferences']['Textures']:
        b=(MODEL_ROOT/rel).read_bytes();w,h=struct.unpack('>II',b[16:24])
        textures.append({'file':rel,'width':w,'height':h,'sha256':hashlib.sha256(b).hexdigest()})
    parameters=[]
    for p in PARAMS.values():
        tags=[tag for tag,ids in [('semantic',set(PRIMARY)),('physics-input',inputs),('physics-output',outputs),('expression',expids),('motion',motionids)] if p['id'] in ids]
        parameters.append({**p,'tags':tags or ['other-rig-parameter']})
    refs=[]
    for r in PHYSICS['PhysicsSettings']:
        for e in r['Input']+r['Output']:
            pid=(e.get('Source') or e['Destination'])['Id']
            if pid not in PARAMS:refs.append({'type':'physics','rig':r['Id'],'id':pid})
    for name,e in EXPRESSIONS.items():
        for p in e['Parameters']:
            if p['Id'] not in PARAMS:refs.append({'type':'expression','name':name,'id':p['Id']})
    for name,m in MOTIONS.items():
        for c in m['Curves']:
            if c['Target']=='Parameter' and c['Id'] not in PARAMS:refs.append({'type':'motion','name':name,'id':c['Id']})
    for m in mapping:
        if m['OutputLive2D'] not in PARAMS:refs.append({'type':'vts-mapping','id':m['OutputLive2D']})
    digest={str(p.relative_to(MODEL_ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in MODEL_ROOT.rglob('*') if p.is_file()}
    result={'parameters':parameters,'expressions':EXPRESSIONS,'motions':MOTIONS,'physics':PHYSICS,
            'physicsInputs':sorted(inputs),'physicsOutputs':sorted(outputs),'externalPhysicsInputs':sorted(inputs-outputs),
            'vtsMappings':mapping,'hotkeys':hotkeys,'vtsPhysics':vts['PhysicsSettings'],'textures':textures,
            'modelGroups':model.get('Groups',[]),'missingReferences':refs,
            'vbridger':{'file':'AdvancedARKitSettings.vbridger','status':'opaque-format-not-executed','bytes':(MODEL_ROOT/'AdvancedARKitSettings.vbridger').stat().st_size},
            'pinnedItems':read_json(MODEL_ROOT/'items_pinned_to_model.json')['Items'],'assetHashes':digest}
    out=ROOT/'web/data/stress-catalog.json';out.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'parameters':len(parameters),'inputs':len(inputs),'outputs':len(outputs),'externalInputs':len(inputs-outputs),'expressions':len(EXPRESSIONS),'motions':len(MOTIONS),'mappings':len(mapping),'hotkeys':len(hotkeys),'missingReferences':refs},ensure_ascii=False))
    return result
if __name__=='__main__':build()
