"""OpenAI function-call dispatcher, independent of a model vendor or SDK.

Pass an OpenAI-shaped tool call on stdin; receive JSON tool output on stdout.
The configured LLM can use this dispatcher in its own tool loop.
"""
import argparse
import json
import sys
from urllib.request import Request,urlopen
from urllib.error import HTTPError

ROUTES={'l2d_capabilities':('GET','/api/capabilities'), 'l2d_state':('GET','/api/state'),
        'l2d_compile':('POST','/api/compile'), 'l2d_execute':('POST','/api/execute'), 'l2d_stop':('POST','/api/stop')}

def tool_schemas():
    tools=[]
    descriptions={'l2d_capabilities':'读取当前模型真实动作、语义参数、范围和限制。编排前先调用。',
                  'l2d_state':'读取舞台就绪状态和任务实际回执；只有 completed / progress=1 才代表表演完成。',
                  'l2d_compile':'校验语义动作计划的范围、时长与通道冲突，不执行。',
                  'l2d_execute':'执行通过校验的语义动作计划；得到 jobId 后用 l2d_state 追踪到完成。',
                  'l2d_stop':'停止当前表演并平滑回到待机。'}
    for name in ROUTES:
        params={'type':'object','properties':{},'additionalProperties':False}
        if name in ('l2d_compile','l2d_execute'):
            params['properties']['plan']={'type':'object','description':'version:1 的动作计划；动作和参数必须来自 l2d_capabilities。'}
            params['required']=['plan']
        if name=='l2d_execute':
            params['properties']['backend']={'type':'string','enum':['web','vts'],'description':'执行后端；省略使用当前选择'}
            params['properties']['requestId']={'type':'string','description':'可选指令箱请求 ID'}
        tools.append({'type':'function','function':{'name':name,'description':descriptions[name],'parameters':params}})
    return tools

def dispatch(call,base):
    fn=call.get('function',call);name=fn.get('name')
    if name not in ROUTES:raise ValueError('未知 Live2D 工具')
    args=fn.get('arguments',{})
    if isinstance(args,str):args=json.loads(args)
    if not isinstance(args,dict):raise ValueError('工具参数需要 JSON 对象')
    method,path=ROUTES[name]
    req=Request(base.rstrip('/')+path,headers={'Content-Type':'application/json'},
                data=json.dumps(args,ensure_ascii=False).encode('utf8') if method=='POST' else None,method=method)
    try:
        with urlopen(req,timeout=10) as r:return json.load(r)
    except HTTPError as e:return {'error':json.loads(e.read()).get('error','本地接口失败'),'status':e.code}

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');sys.stdin.reconfigure(encoding='utf-8-sig')
    p=argparse.ArgumentParser();p.add_argument('--schemas',action='store_true');p.add_argument('--url',default='http://127.0.0.1:61942');a=p.parse_args()
    try:r=tool_schemas() if a.schemas else dispatch(json.load(sys.stdin),a.url)
    except (ValueError,OSError) as e:r={'error':str(e)}
    print(json.dumps(r,ensure_ascii=False))
