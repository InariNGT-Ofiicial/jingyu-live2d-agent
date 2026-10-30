"""Strict offline VTS calibration exporter. No connection, token or host mutation.

One tracking input may drive several outputs. Independent bridge motion is not
silently approximated when the author's original mapping cannot represent it.
"""
import math
from compiler import compile_plan
from model_profile import MODEL_ROOT,read_json,PARAMS

def sample(points,t):
    if t<=points[0][0]:return points[0][1]
    for (a,x),(b,y) in zip(points,points[1:]):
        if t<=b:
            u=max(0,min(1,(t-a)/max(b-a,1e-8)));return x+(y-x)*u*u*(3-2*u)
    return points[-1][1]

def inverse(mapping,value):
    lo,hi=mapping['OutputRangeLower'],mapping['OutputRangeUpper']
    if hi==lo:raise ValueError('constant output mapping')
    return mapping['InputRangeLower']+(value-lo)/(hi-lo)*(mapping['InputRangeUpper']-mapping['InputRangeLower'])

def export_calibration(plan,fps=30):
    if isinstance(fps,bool) or not isinstance(fps,int) or not 2<=fps<=60:raise ValueError('fps must be 2..60')
    c=compile_plan(plan);settings=read_json(MODEL_ROOT/'大肥鱼.vtube.json')['ParameterSettings']
    mappings={}
    for m in settings:
        if m['Input']:mappings.setdefault(m['OutputLive2D'],[]).append(m)
    ids={t['id'] for t in c['tracks']}; blockers=[];frames=[]
    for pid in sorted(ids):
        if len(mappings.get(pid,[]))!=1:blockers.append({'parameter':pid,'reason':'no unique author tracking mapping'})
    used_inputs={mappings[pid][0]['Input'] for pid in ids if len(mappings.get(pid,[]))==1}
    for source in sorted(used_inputs):
        siblings={m['OutputLive2D'] for m in settings if m['Input']==source}-ids
        if siblings:blockers.append({'input':source,'outputs':sorted(siblings),'reason':'author input also writes outputs absent from this plan'})
    if not blockers:
        for index in range(math.ceil(c['duration']*fps)+1):
            time=min(index/fps,c['duration']);values={id:PARAMS[id]['default'] for id in ids};expressions=[]
            for tr in c['tracks']:
                t=time-tr['start']
                if not 0<=t<=tr['duration']:continue
                if tr.get('expression'):expressions.append((tr,t))
                else:values[tr['id']]=sample(tr['points'],t)
            for tr,t in expressions:
                e=tr['expression'];w=sample(e['weightPoints'],t);base=values[tr['id']];v=e['value']
                values[tr['id']]=base+v*w if e['blend']=='Add' else base*(1+(v-1)*w) if e['blend']=='Multiply' else base+(v-base)*w
            inputs={};sources={}
            for pid,value in values.items():
                p=PARAMS[pid];m=mappings[pid][0];value=max(p['min'],min(p['max'],value));x=inverse(m,value);source=m['Input']
                if source in inputs and abs(inputs[source]-x)>1e-4:
                    blockers.append({'time':round(time,4),'input':source,'outputs':[sources[source],pid],'reason':'shared author input requires incompatible values'});break
                inputs[source]=x;sources[source]=pid
            if blockers:break
            frames.append({'time':round(time,5),'request':{'apiName':'VTubeStudioPublicAPI','apiVersion':'1.0','requestID':f'calibration-{index}',
                           'messageType':'InjectParameterDataRequest','data':{'faceFound':True,'mode':'set','parameterValues':[{'id':id,'value':round(v,6),'weight':1} for id,v in sorted(inputs.items())]}}})
    return {'backend':'VTubeStudioPublicAPI','mode':'offline-calibration','representable':not blockers,'fps':fps,'duration':c['duration'],
            'blockers':blockers,'frames':[] if blockers else frames,
            'notes':['No VTS host was connected or authenticated.','These are unsmoothed input targets; VTS smoothing and physics require separate visual calibration.',
                     'Native gestures/expressions without tracking mappings require an explicit VTS hotkey/expression adapter; they are not replaced by arbitrary movements.']}
