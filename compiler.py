"""Semantic action IR -> bounded, eased parameter tracks. Never parses prose."""
import math
from copy import deepcopy
from model_profile import PARAMS, PRIMARY, EXPRESSIONS, MOTIONS, GESTURES, GESTURE_JOINTS, PHYSICS

PHYSICS_OUTPUTS={o['Destination']['Id'] for s in PHYSICS['PhysicsSettings'] for o in s['Output']}

class CompileError(ValueError):
    pass

def number(value, name, low, high):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise CompileError(f'{name} 必须是有限数字')
    if not low <= value <= high:
        raise CompileError(f'{name} 超出范围 {low}..{high}')
    return float(value)

def cubic(a,b,c,d,t):
    return (1-t)**3*a + 3*(1-t)**2*t*b + 3*(1-t)*t*t*c + t**3*d

def sample_motion(segments, t):
    prev=(segments[0], segments[1]); i=2
    while i < len(segments):
        kind=int(segments[i]); i+=1
        if kind==1:
            c1=segments[i:i+2]; c2=segments[i+2:i+4]; end=segments[i+4:i+6]; i+=6
        else:
            end=segments[i:i+2]; i+=2
        if t<=end[0]:
            if kind==0:
                u=max(0,min(1,(t-prev[0])/max(1e-8,end[0]-prev[0])))
                return prev[1]+(end[1]-prev[1])*u
            if kind==2: return prev[1]
            if kind==3: return end[1]
            lo=0.; hi=1.
            for _ in range(18):
                u=(lo+hi)/2
                if cubic(prev[0],c1[0],c2[0],end[0],u)<t: lo=u
                else: hi=u
            return cubic(prev[1],c1[1],c2[1],end[1],(lo+hi)/2)
        prev=end
    return prev[1]

def compile_plan(plan):
    if not isinstance(plan,dict) or type(plan.get('version')) is not int or plan.get('version') != 1:
        raise CompileError('动作计划需要 version: 1')
    actions=plan.get('actions')
    if not isinstance(actions,list) or not 1<=len(actions)<=24:
        raise CompileError('actions 必须包含 1..24 个动作')
    if len(str(plan.get('intent',''))) > 2000 or len(str(plan.get('summary',''))) > 1000:
        raise CompileError('动作说明过长')
    tracks=[]; steps=[]; warnings=[]
    def add(pid, start, duration, points, index, label, expression=None):
        if pid not in PARAMS: raise CompileError(f'模型没有参数 {pid}')
        if pid in PHYSICS_OUTPUTS: raise CompileError(f'{pid} 归作者物理控制，不能直接驱动')
        p=PARAMS[pid]
        clipped=[]
        for t,v in points:
            if not math.isfinite(v): raise CompileError('参数曲线包含非有限值')
            c=max(p['min'],min(p['max'],v))
            if c!=v: warnings.append(f'{pid} 已限制到模型范围')
            clipped.append([round(t,5),round(c,6)])
        for old in tracks:
            if old['id']==pid and old['action']!=index and min(old['start']+old['duration'],start+duration)-max(old['start'],start)>0.015:
                old_expr=old.get('expression')
                overlay=expression or old_expr
                base_kind=actions[old['action']]['kind'] if expression else actions[index]['kind']
                if not (bool(expression)!=bool(old_expr) and overlay.get('layer')=='overlay' and pid in PRIMARY and base_kind!='gesture'):
                    raise CompileError(f'动作 {old["action"]+1} 与 {index+1} 同时控制 {pid}，请错开时间或使用明确的 expression overlay')
        track={'id':pid,'start':round(start,4),'duration':round(duration,4),'points':clipped,'action':index,'label':label,
               'owner':'expression' if expression else 'native-gesture' if actions[index]['kind']=='gesture' else 'semantic',
               'stage':'expression' if expression else 'motion'}
        if expression:track['expression']=expression
        tracks.append(track)
    def hold(pid,value,index,label,at,duration,fade=.42):
        d=PARAMS[pid]['default']; fade=min(fade,duration*.28)
        add(pid,at,duration,[(0,d),(fade,value),(duration-fade,value),(duration,d)],index,label)
    def waves(pid,amp,index,label,at,duration,count,symmetric=False):
        d=PARAMS[pid]['default']; points=[(0,d),(.12*duration,d-amp*.16)]
        for n in range(count):
            st=.17*duration+n*.66*duration/count; w=.66*duration/count
            points += [(st,d),(st+w*.32,d+amp*(1-.1*n)),(st+w*.76,d-amp*(.85 if symmetric else .18))]
        points += [(duration,d)]
        add(pid,at,duration,sorted(points),index,label)
    for index, action in enumerate(actions):
        if not isinstance(action,dict): raise CompileError('每个动作必须是对象')
        kind=action.get('kind'); at=number(action.get('at',0),'at',0,59)
        duration=number(action.get('duration',2.5),'duration',.2,20)
        strength=number(action.get('strength',.6),'strength',0,1)
        count=action.get('count',1)
        if isinstance(count,bool) or not isinstance(count,int) or not 1<=count<=4: raise CompileError('count 必须为 1..4 的整数')
        label=''
        if kind=='look':
            direction=action.get('direction','center')
            if direction not in ['left','right','up','down','center']: raise CompileError('不支持的视线方向')
            label={'left':'看向左侧','right':'看向右侧','up':'抬眼看上方','down':'低头看下方','center':'看向你'}[direction]
            x={'left':-1,'right':1}.get(direction,0); y={'up':1,'down':-1}.get(direction,0)
            head_delay=min(.09,duration*.15);body_delay=min(.19,duration*.3)
            # Screen-left maps to negative head and eyeball input in this model.
            if x or direction=='center':
                hold('ParamEyeBallX',x*.75*strength,index,label,at,duration,.22)
                hold('AngleX',x*23*strength,index,label,at+head_delay,duration-head_delay)
                hold('PositionX',x*5*strength,index,label,at+body_delay,duration-body_delay)
            if y:
                hold('ParamEyeBallY',y*.6*strength,index,label,at,duration,.22)
                hold('AngleY',y*18*strength,index,label,at+head_delay,duration-head_delay)
        elif kind in ['nod','shake_head']:
            label='点头'+str(count)+'次' if kind=='nod' else '轻轻摇头'+str(count)+'次'
            if duration < count*.45: raise CompileError('重复点头／摇头的时间太短，请至少每次 0.45 秒')
            waves('AngleY' if kind=='nod' else 'AngleX',(-15 if kind=='nod' else 20)*strength,index,label,at,duration,count,kind=='shake_head')
            waves('PositionY' if kind=='nod' else 'PositionX',(-3 if kind=='nod' else 4)*strength,index,label,at+.08,duration-.08,count,kind=='shake_head')
        elif kind=='tilt':
            direction=action.get('direction','left')
            if direction not in ['left','right']: raise CompileError('歪头方向需要 left 或 right')
            label='轻轻歪头'; sign=-1 if direction=='left' else 1
            hold('AngleZ',sign*15*strength,index,label,at,duration)
            hold('PositionZ',-sign*3*strength,index,label,at+.1,duration-.1)
        elif kind=='smile':
            label='自然微笑'
            for pid,v in [('ParamMouthForm',.8),('EyeSmile',.65),('MouthSmile_L',.55),('MouthSmile_R',.55)]:
                hold(pid,v*strength,index,label,at,duration)
        elif kind=='blink':
            side=action.get('side','both')
            if side not in ['both','left','right']: raise CompileError('眨眼 side 需要 both / left / right')
            label='眨眼' if side=='both' else '单眼眨眼'
            if duration<count*.22: raise CompileError('眨眼频率过高')
            for pid in (['ParamEyeLOpen','ParamEyeROpen'] if side=='both' else ['ParamEyeLOpen' if side=='left' else 'ParamEyeROpen']):
                points=[(0,1)]
                for n in range(count):
                    t=(n+.3)*duration/count; w=min(.32,duration/count*.65)
                    points += [(t,1),(t+w*.28,0),(t+w*.48,0),(t+w,1)]
                points += [(duration,1)]
                add(pid,at,duration,sorted(points),index,label)
        elif kind=='expression':
            name=action.get('name')
            if name not in EXPRESSIONS: raise CompileError(f'未知表情 {name}；请读取 capabilities')
            label=name
            layer=action.get('layer','exclusive')
            if layer not in ['exclusive','overlay']:raise CompileError('expression.layer 需要 exclusive 或 overlay')
            for item in EXPRESSIONS[name]['Parameters']:
                pid=item['Id']; d=PARAMS[pid]['default']; v=item['Value']; blend=item.get('Blend','Add')
                if blend not in ['Add','Multiply','Overwrite']:raise CompileError('不支持的作者表情混合方式')
                target=d+v*strength if blend=='Add' else d*(1+(v-1)*strength) if blend=='Multiply' else d+(v-d)*strength
                fade=min(.42,duration*.28)
                add(pid,at,duration,[(0,d),(fade,target),(duration-fade,target),(duration,d)],index,label,
                    expression={'blend':blend,'value':v,'layer':layer,'weightPoints':[[0,0],[fade,strength],[duration-fade,strength],[duration,0]]})
        elif kind=='gesture':
            name=action.get('name')
            if name not in GESTURES: raise CompileError(f'未知手势 {name}')
            g=GESTURES[name]; label=g['label']; enter=MOTIONS[g['enter']]; exit=MOTIONS[g['exit']]
            in_d=enter['Meta']['Duration']; out_d=exit['Meta']['Duration']
            if duration<in_d+out_d+.35:
                duration=in_d+out_d+.35; warnings.append(f'{label} 已延长以保留作者的进入与收回动作')
            accents=action.get('accents',[])
            if not isinstance(accents,list) or len(accents)>12: raise CompileError('手势 accents 需要 0..12 段')
            joint_cues={}
            for cue in accents:
                if not isinstance(cue,dict): raise CompileError('关节片段必须是对象')
                st=number(cue.get('at'),'关节 at',in_d,duration-out_d)
                dur=number(cue.get('duration'),'关节 duration',.4,20)
                if st+dur>duration-out_d: raise CompileError('关节片段不可覆盖作者退出动作')
                values=cue.get('values')
                if not isinstance(values,dict) or not 1<=len(values)<=5: raise CompileError('关节 values 需要 1..5 个控制')
                for joint,value in values.items():
                    if joint not in GESTURE_JOINTS[name]: raise CompileError(f'{name} 没有可写关节 {joint}')
                    pid=GESTURE_JOINTS[name][joint]; p=PARAMS[pid]
                    val=number(value,joint,p['min'],p['max'])
                    cues=joint_cues.setdefault(pid,[])
                    if any(min(st+dur,s+d)-max(st,s)>0 for s,d,_ in cues): raise CompileError(f'同一关节 {joint} 的片段重叠')
                    cues.append((st,dur,val))
            ids=sorted({c['Id'] for m in (enter,exit) for c in m['Curves'] if c['Target']=='Parameter'})
            for pid in ids:
                default=PARAMS[pid]['default']; points=[(0,default)]
                prev=default
                for m,offset in [(enter,0),(exit,duration-out_d)]:
                    curve=next((c for c in m['Curves'] if c['Id']==pid and c['Target']=='Parameter'),None)
                    md=m['Meta']['Duration']
                    if curve:
                        count_s=max(2,math.ceil(md*45))
                        samples=[(offset+k*md/count_s,sample_motion(curve['Segments'],k*md/count_s)) for k in range(count_s+1)]
                        points+=samples; prev=samples[-1][1]
                    else: points += [(offset,prev),(offset+md,prev)]
                # Always restore the author's neutral state after the authored exit.
                points += [(duration+.12,default)]
                if pid in joint_cues:
                    curve=next(c for c in enter['Curves'] if c['Id']==pid and c['Target']=='Parameter')
                    rest=sample_motion(curve['Segments'],in_d)
                    for st,dur,val in joint_cues[pid]:
                        fade=min(.5,dur*.28)
                        points += [(st,rest),(st+fade,val),(st+dur-fade,val),(st+dur,rest)]
                unique={round(t,5):v for t,v in points}
                add(pid,at,duration+.12,sorted(unique.items()),index,label)
            duration+=.12
        elif kind=='talk':
            label='说话口型（无音频）'; points=[(0,0)]
            for k in range(1,math.ceil(duration*8)):
                t=k/8
                if t<duration-.2: points.append((t,(.15+.48*abs(math.sin(k*2.31)))*strength))
            points.append((duration,0)); add('ParamMouthOpenY',at,duration,points,index,label)
        elif kind=='trajectory':
            frames=action.get('frames')
            if not isinstance(frames,list) or not 2<=len(frames)<=60:
                raise CompileError('trajectory.frames 需要 2..60 个关键帧')
            label=str(action.get('label','连续动作'))[:60]
            ids=None; previous=0.; paths={}
            for frame in frames:
                if not isinstance(frame,dict): raise CompileError('关键帧必须是对象')
                t=number(frame.get('time'),'关键帧 time',.15,duration-.15)
                if t-previous<.08-1e-8: raise CompileError('关键帧必须按时间递增，间隔至少 0.08 秒')
                previous=t; values=frame.get('values')
                if not isinstance(values,dict) or not 1<=len(values)<=12: raise CompileError('关键帧需要 1..12 个输入参数')
                if ids is None: ids=set(values)
                if set(values)!=ids: raise CompileError('每个关键帧必须包含相同输入参数')
                for pid,value in values.items():
                    if pid not in PRIMARY or pid=='ParamBreath': raise CompileError(f'{pid} 不是可写的语义输入')
                    p=PARAMS[pid]; v=number(value,pid,p['min'],p['max'])
                    paths.setdefault(pid,[(0,p['default'])]).append((t,v))
            for pid,points in paths.items():
                add(pid,at,duration,points+[(duration,PARAMS[pid]['default'])],index,label)
        elif kind=='pose':
            values=action.get('values')
            if not isinstance(values,dict) or not values or len(values)>12: raise CompileError('pose.values 需要 1..12 个输入参数')
            label=str(action.get('label','自定义姿态'))[:60]
            for pid,value in values.items():
                if pid not in PRIMARY or pid=='ParamBreath': raise CompileError(f'{pid} 不是可写的语义输入')
                p=PARAMS[pid]; v=number(value,pid,p['min'],p['max'])
                hold(pid,v,index,label,at,duration)
        else:
            raise CompileError(f'不支持动作 {kind}；请读取 /api/capabilities，不会用无关动作替代')
        steps.append({'index':index,'label':label,'kind':kind,'start':at,'duration':round(duration,4)})
    total=max(t['start']+t['duration'] for t in tracks)+.7
    if total>60: raise CompileError('动作总长不可超过 60 秒')
    return {'version':1,'driverVersion':'1.2.0','intent':str(plan.get('intent','')),'summary':str(plan.get('summary','')),
            'duration':round(total,4),'tracks':tracks,'steps':steps,'warnings':sorted(set(warnings)),
            'sourcePlan':deepcopy(plan),'policy':{'returnToIdle':True,'physics':'author-131-rigs','easing':'smoothstep','parameterLimits':'moc3-core'}}
