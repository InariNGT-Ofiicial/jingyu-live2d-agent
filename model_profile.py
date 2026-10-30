"""Read-only catalog of the author's received model. No model files are changed."""
from pathlib import Path
import json
import os

ROOT = Path(__file__).resolve().parent
BUNDLED_MODEL = ROOT/'model'/'DeepSeek'
MODEL_ROOT = Path(os.getenv('L2D_MODEL_DIR') or (BUNDLED_MODEL if BUNDLED_MODEL.is_dir() else ROOT.parent / 'DeepSeek-L2D' / 'DeepSeek免费公皮' / 'DeepSeek')).resolve()
def read_json(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))

CORE = read_json(ROOT / 'core-inventory.json')
PARAMS = {p['id']: p for p in CORE['parameters']}
DISPLAY = read_json(MODEL_ROOT / '大肥鱼.cdi3.json')
for item in DISPLAY['Parameters']:
    PARAMS[item['Id']]['name'] = item['Name']
EXPRESSIONS = {p.name.removesuffix('.exp3.json'): read_json(p) for p in (MODEL_ROOT/'Exp3').glob('*.json')}
MOTIONS = {p.name.removesuffix('.motion3.json'): read_json(p) for p in (MODEL_ROOT/'Animation').glob('*.json')}
PHYSICS = read_json(MODEL_ROOT/'大肥鱼.physics3.json')
PRIMARY = ['AngleX','AngleY','AngleZ','PositionX','PositionY','PositionZ','LeanInput',
           'ParamEyeBallX','ParamEyeBallY','ParamEyeLOpen','ParamEyeROpen','ParamMouthForm','ParamMouthOpenY',
           'EyeSmile','MouthSmile_L','MouthSmile_R','ParamBrowLY','ParamBrowRY',
           'BrowInnerUp','CheeckPuff','JawOpen','ParamBreath',
           'Mouthpucker','MouthFunnel','MouthX','MouthPressLipOpen','MouthPuckerWiden',
           'REyeSquint','LEyeSquint','TongueOut','NoseNeer','MouthRollUpper','MouthRollLower']
GESTURES = {
    'hand_on_chest': {'label':'抚胸致意', 'enter':'默认手切举手', 'exit':'举手切默认手'},
    'point': {'label':'竖起食指', 'enter':'竖手指切出来动画', 'exit':'竖手指切回默认'},
    'grass': {'label':'拿起狗尾草', 'enter':'狗尾草切换出来', 'exit':'狗尾草切回默认手'},
}
GESTURE_JOINTS = {
    'hand_on_chest': {'upperArm':'Param62','perspective':'Param59','forearm':'Param60','wrist':'Param61'},
    'point': {'upperArm':'Param36','perspective':'Param39','forearm':'Param41','wrist':'Param42','finger':'Param43'},
    'grass': {'upperArm':'Param36','perspective':'Param39','forearm':'Param41','wrist':'Param42'},
}
ACTION_SCHEMA = {
    'trajectory': {'frames':'2..60 个 {time, values}；time 为动作内秒数，间隔至少 0.08 秒，距首尾至少 0.15 秒；每帧相同的 1..12 个语义输入', 'note':'连续多轴表演；中间不强制回正，首尾自动回到默认值；参数权限与 pose 相同'},
    'look': {'direction':['left','right','up','down','center'], 'note':'左右以观众屏幕为准；视线先于头部'},
    'nod': {'count':'1..4', 'note':'点头带预备、两次轻微幅度变化与回正'},
    'shake_head': {'count':'1..4', 'note':'温和左右摇头'},
    'tilt': {'direction':['left','right'], 'note':'侧倾头部，身体轻微反向平衡'},
    'smile': {'note':'嘴角、眼型与眼睑一起变化'},
    'blink': {'side':['both','left','right'], 'count':'1..4'},
    'expression': {'name': list(EXPRESSIONS), 'layer':['exclusive','overlay'], 'note':'运行时对基础值应用 Add/Multiply/Overwrite；默认独占。overlay 仅允许与语义输入轨迹叠加，不能覆盖原生手势或另一表情'},
    'gesture': {'name': list(GESTURES), 'joints':GESTURE_JOINTS, 'accents':'可选 0..12 段 {at,duration,values:{joint:value}}；时间相对手势起点，仅在进入结束与退出开始之间；值 -1..1', 'note':'使用作者原动作进入与退出；关节变化仅限该手势有效姿态，自动收回'},
    'talk': {'note':'仅口型节奏，不生成语音或音频'},
    'pose': {'values': {p: [PARAMS[p]['min'],PARAMS[p]['max']] for p in PRIMARY if p != 'ParamBreath'}, 'note':'只允许语义输入参数；不能直接写物理输出'},
}

def capabilities():
    return {'model':'DeepSeek-chan · 大肥鱼', 'bridgeVersion':'1.2.0',
            'counts':{ 'parameters':CORE['parameterCount'], 'parts':CORE['partCount'], 'drawables':CORE['drawableCount'],
                       'physics':len(PHYSICS['PhysicsSettings']), 'motions':len(MOTIONS), 'expressions':len(EXPRESSIONS)},
            'actions':ACTION_SCHEMA, 'gestures':GESTURES,
            'driverStages':['idle','gaze','motion','blink','expression','commit','author-physics','render'],
            'planSchema':{'version':1,'intent':'用户原始自然语言','summary':'动作说明','actions':[{'kind':'nod','at':0,'duration':2.5,'strength':0.55,'count':2}]},
            'timing':{'at':'seconds >=0','duration':'seconds 0.2..20','strength':'0..1','maxPlanSeconds':60,'maxActions':24},
            'unsupported':['没有自由行走、跑步、转身等完整骨骼动画；不可声称已执行这些动作','没有 TTS / 语音识别','自由文本需通过已配置的 DSH/OpenAI 兼容服务或外部 Agent 编排'],
            'parameters':[PARAMS[p] for p in PRIMARY],
            'experimentalInputs':{'ids':['NoseNeer','MouthRollUpper','MouthRollLower'], 'note':'作者配置存在，但 neutral/talk/turned 三种 Core 几何探测未发现可见变化；不保证有表演效果'},
            'source':'神宫凉子（原画及拆分） / 霓虹猫_NeonNeko（Live2D 建模）'}

def write_profile():
    folder = ROOT/'web'/'data'
    folder.mkdir(parents=True, exist_ok=True)
    vts=read_json(MODEL_ROOT/'大肥鱼.vtube.json')
    output_ids={o['Destination']['Id'] for s in PHYSICS['PhysicsSettings'] for o in s['Output']}
    gesture_ids={c['Id'] for g in GESTURES.values() for mode in ['enter','exit'] for c in MOTIONS[g[mode]]['Curves'] if c['Target']=='Parameter'}
    expression_ids={p['Id'] for e in EXPRESSIONS.values() for p in e['Parameters']}
    catalog={id:{'owner':'author-physics' if id in output_ids else 'semantic' if id in PRIMARY else 'native-gesture' if id in gesture_ids else 'author-expression' if id in expression_ids else 'unmapped',
                 'min':p['min'],'max':p['max'],'default':p['default']} for id,p in PARAMS.items()}
    profile = {**capabilities(), 'allParameters':list(PARAMS.values()),'idleMotion':MOTIONS['IDLE'],
               'controlCatalog':catalog,'vtsMappings':vts['ParameterSettings'],
               'physicsInputIds':sorted({i['Source']['Id'] for s in PHYSICS['PhysicsSettings'] for i in s['Input']}),
               'physicsOutputIds':sorted({o['Destination']['Id'] for s in PHYSICS['PhysicsSettings'] for o in s['Output']})}
    (folder/'model-profile.json').write_text(json.dumps(profile,ensure_ascii=False),encoding='utf-8')
    return profile

if __name__ == '__main__':
    p=write_profile()
    print(json.dumps(p['counts'],ensure_ascii=False))
