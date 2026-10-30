"""Provider-neutral natural language -> validated Live2D semantic plan.

Only text and the model's semantic capability catalog leave the computer.
API credentials stay in server memory, never in browser storage or job records.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

from compiler import compile_plan, CompileError
from model_profile import ROOT, capabilities


class PlannerError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def endpoint(base, protocol):
    if not isinstance(base, str) or len(base) > 1000:
        raise PlannerError('Base URL 无效')
    u = urlsplit(base.strip())
    if u.scheme not in ('http', 'https') or not u.hostname or u.username or u.password or u.query or u.fragment:
        raise PlannerError('Base URL 需要 http(s) 地址，不含账号、查询参数或片段')
    if u.scheme == 'http' and u.hostname not in ('localhost', '127.0.0.1', '::1'):
        raise PlannerError('远程服务请使用 HTTPS；HTTP 仅用于本机服务')
    suffix = '/responses' if protocol == 'responses' else '/chat/completions'
    p = u.path.rstrip('/')
    for end in ('/chat/completions', '/responses'):
        if p.endswith(end):
            p = p[:-len(end)]
            break
    return urlunsplit((u.scheme, u.netloc, p + suffix, '', ''))


def parse_plan(text):
    if not isinstance(text, str) or not text.strip():
        raise PlannerError('模型没有返回动作计划')
    text = text.strip()
    match = re.fullmatch(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if match:
        text = match.group(1)
    def invalid(x):
        raise PlannerError('模型返回了非有限数字')
    try:
        obj = json.loads(text, parse_constant=invalid)
    except (ValueError, TypeError):
        raise PlannerError('模型输出不是完整 JSON，请换用能遵循 JSON 指令的模型') from None
    if not isinstance(obj, dict):
        raise PlannerError('动作计划必须是 JSON 对象')
    if obj.get('unsupported') is True or obj.get('refusal'):
        raise PlannerError(str(obj.get('reason') or obj.get('refusal') or '该要求超出模型能力')[:400])
    return obj.get('plan', obj)


def output_text(obj, protocol):
    if not isinstance(obj,dict):raise PlannerError('服务响应必须为 JSON 对象')
    try:
        if protocol == 'responses':
            if obj.get('status') == 'incomplete':
                raise PlannerError('模型输出未完成，请调整服务配置')
            if isinstance(obj.get('output_text'), str):
                return obj['output_text']
            parts = [c for item in obj.get('output', []) if item.get('type') == 'message' for c in item.get('content', [])]
            if any(p.get('type') == 'refusal' for p in parts):
                raise PlannerError('模型拒绝了本次编排')
            return ''.join(p['text'] for p in parts if p.get('type') == 'output_text')
        choice = obj['choices'][0]
        if choice.get('finish_reason') in ('length', 'content_filter'):
            raise PlannerError('模型输出被截断或过滤，请调整服务配置')
        msg = choice['message']
        if msg.get('refusal'):
            raise PlannerError('模型拒绝了本次编排')
        content = msg.get('content')
        if isinstance(content, list):
            return ''.join(p.get('text', '') for p in content if p.get('type') in ('text', 'output_text'))
        return content
    except (KeyError, TypeError, IndexError):
        raise PlannerError('服务响应不符合所选 OpenAI 接口格式') from None


def system_prompt():
    cap = capabilities()
    catalog = {k: cap[k] for k in ('actions', 'timing', 'gestures', 'parameters', 'experimentalInputs')}
    return '''你是鲸语 Live2D 动作编排器。将用户的情境编为一个可执行的 JSON 计划。
只能使用下面能力目录里的动作与语义输入；不要调用工具、读取文件或执行代码。
actions 中每个对象必须用 kind 指定动作类型，不是 type、action 或 name。kind 可取
trajectory/look/nod/shake_head/tilt/smile/blink/expression/gesture/talk/pose。
只返回 JSON，不要解释、Markdown 或思考过程。格式：
{"version":1,"title":"短标题","intent":"用户意图","summary":"表演说明","view":"portrait","actions":[...]}
每段动作 at 为秒，duration 0.2..20，strength 0..1；总时长最多60秒，最多24段动作。
同一参数上的动作不能重叠；look 会占用头/身体/眼球，smile 会占用嘴型/眼型。
gesture 使用 hand_on_chest、point 或 grass，每段至少7秒，并避免两种手势同时出现。
需要连续表演时优先一个 trajectory：frames 内 time 是该动作内秒数，所有帧相同1..12个输入；
首帧在0.2秒以后、末帧在结束前0.2秒以前，至少2帧，帧间隔至少0.08秒。
可以把头眼和身体轨迹、原生gesture、互不冲突的smile和blink按情绪节奏并行。
表情expression仅用目录里的name；默认exclusive，只有确实需要叠加到语义输入时才设layer:overlay。
不要添加目录以外的控制，不直接写物理输出，不承诺自由走路、跑步、转身、语音或音频。
无法实现时返回 {"unsupported":true,"reason":"清楚说明限制"}，不要拿无关动作替代。
未经用户要求，不改变成人体型或服装。动作必须起承转合，结束后回到待机。
完全有效的示例（可调整，注意每个动作都有 kind）：
{"version":1,"title":"侧目后抚胸致意","intent":"轻轻侧目，再抚胸微笑","view":"portrait","actions":[{"kind":"trajectory","at":0,"duration":12,"frames":[{"time":1,"values":{"AngleX":-18,"AngleY":-6,"AngleZ":8,"PositionX":-8,"ParamEyeBallX":-0.5}},{"time":4,"values":{"AngleX":7,"AngleY":4,"AngleZ":-6,"PositionX":5,"ParamEyeBallX":0.2}},{"time":9,"values":{"AngleX":-3,"AngleY":0,"AngleZ":2,"PositionX":0,"ParamEyeBallX":0}}]},{"kind":"gesture","name":"hand_on_chest","at":3,"duration":8},{"kind":"smile","at":3,"duration":8,"strength":0.6},{"kind":"blink","at":9,"duration":0.6,"count":1}]}
能力目录：\n''' + json.dumps(catalog, ensure_ascii=False, separators=(',', ':'))


class Planner:
    def __init__(self,storage=None):
        self.lock = threading.RLock()
        self.storage=Path(storage) if storage else None
        self.config = {'provider': 'openai', 'protocol': 'chat_completions',
                       'baseUrl': os.getenv('L2D_LLM_BASE_URL', 'https://api.openai.com/v1'),
                       'model': os.getenv('L2D_LLM_MODEL', ''), 'jsonMode': False,
                       'apiKey': os.getenv('L2D_LLM_API_KEY', os.getenv('OPENAI_API_KEY', ''))}
        self.dsh_command = os.getenv('L2D_DSH_COMMAND') or shutil.which('dsh')
        self.config['provider']=os.getenv('L2D_LLM_PROVIDER','dsh' if self.dsh_command and not self.config['model'] else 'openai')
        if self.storage and self.storage.is_file():
            try:
                saved=json.loads(self.storage.read_text(encoding='utf-8'))
                self.configure({k:v for k,v in saved.items() if k!='apiKey'})
            except (ValueError,OSError,TypeError):pass

    def public(self):
        with self.lock:
            return {**{k:v for k,v in self.config.items() if k != 'apiKey'},
                    'hasApiKey': bool(self.config['apiKey']), 'dshAvailable': bool(self.dsh_command),
                    'ready': self.config['provider'] == 'dsh' and bool(self.dsh_command) or bool(self.config['model'])}

    def configure(self, data):
        allowed = ('provider', 'protocol', 'baseUrl', 'model', 'jsonMode', 'apiKey')
        with self.lock:
            c = dict(self.config)
            c.update({k:v for k,v in data.items() if k in allowed})
            if c['baseUrl']!=self.config['baseUrl'] and 'apiKey' not in data:c['apiKey']=''
            if c['provider'] not in ('openai', 'dsh') or c['protocol'] not in ('chat_completions', 'responses'):
                raise PlannerError('不支持的编排来源或协议')
            if not isinstance(c['model'], str) or len(c['model']) > 200 or any(ord(x) < 32 for x in c['model']):
                raise PlannerError('模型名称无效')
            if not isinstance(c['apiKey'], str) or len(c['apiKey']) > 8192 or any(x in c['apiKey'] for x in ('\r','\n')):
                raise PlannerError('API Key 格式无效')
            if type(c['jsonMode']) is not bool:
                raise PlannerError('jsonMode 需要布尔值')
            endpoint(c['baseUrl'], c['protocol'])
            if c['provider'] == 'openai' and not c['model'].strip():
                raise PlannerError('请填写服务提供的模型名称')
            if c['provider'] == 'dsh' and not self.dsh_command:
                raise PlannerError('未找到本机 DSH，请安装 DSH CLI 或使用 OpenAI 兼容接口')
            c['model'] = c['model'].strip()
            if self.storage:
                self.storage.parent.mkdir(parents=True,exist_ok=True)
                tmp=self.storage.with_suffix('.tmp');tmp.write_text(json.dumps({k:v for k,v in c.items() if k!='apiKey'},ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(self.storage)
            self.config = c
            return self.public()

    def chat(self, messages, c):
        payload = {'model': c['model'], 'stream': False}
        if c['protocol'] == 'responses':
            payload.update(input=messages, store=False)
            if c['jsonMode']: payload['text'] = {'format': {'type':'json_object'}}
        else:
            payload['messages'] = messages
            if c['jsonMode']: payload['response_format'] = {'type':'json_object'}
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        if c['apiKey']: headers['Authorization'] = 'Bearer ' + c['apiKey']
        req = Request(endpoint(c['baseUrl'], c['protocol']), data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), headers=headers)
        try:
            with build_opener(NoRedirect()).open(req, timeout=100) as response:
                raw = response.read(3_000_001)
                if len(raw) > 3_000_000: raise PlannerError('模型响应过大')
                obj = json.loads(raw)
        except HTTPError as error:
            # Provider bodies can echo request headers: never surface them.
            raise PlannerError(f'模型服务 HTTP {error.code}；请检查地址、模型、授权与接口模式') from None
        except (URLError, TimeoutError, OSError):
            raise PlannerError('无法连接模型服务或请求超时；请检查本地网络与服务地址') from None
        except (ValueError, UnicodeError):
            raise PlannerError('模型服务没有返回有效 JSON 响应') from None
        return output_text(obj, c['protocol'])

    def dsh(self, messages):
        if not self.dsh_command: raise PlannerError('本机未安装 DSH CLI')
        task = '\n\n'.join(m['content'] for m in messages)
        creation = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        command = [self.dsh_command, '--profile', 'headless', '--patch', str(ROOT/'dsh-planner.patch.yml'), '-']
        try:
            # The installed DSH launcher owns its credentials. No credentials are read or copied here.
            result = subprocess.run(command, input=task, text=True, encoding='utf-8', errors='replace',
                                    capture_output=True, timeout=150, cwd=str(ROOT), creationflags=creation)
        except subprocess.TimeoutExpired:
            raise PlannerError('DSH 编排超时，请在 DSH 检查模型连接后重试') from None
        except OSError:
            raise PlannerError('无法启动本机 DSH CLI') from None
        if result.returncode:
            raise PlannerError('DSH 编排失败，请在 DSH 检查当前账号与模型配置')
        # headless writes the final answer to stdout and diagnostics to stderr.
        return '\n'.join(line for line in result.stdout.splitlines()
                         if not line.startswith('[llm-deepseek-account]')).strip()

    def plan(self, prompt, update=None):
        if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 2000:
            raise PlannerError('请输入 1..2000 字的动作要求')
        with self.lock:
            c = dict(self.config)
        if c['provider'] == 'openai' and not c['model']:
            raise PlannerError('请先配置模型接口')
        messages = [{'role':'system','content':system_prompt()}, {'role':'user','content':prompt.strip()}]
        start = time.monotonic()
        for attempt in range(2):
            if update: update('generating' if attempt == 0 else 'repairing')
            text = self.dsh(messages) if c['provider'] == 'dsh' else self.chat(messages, c)
            try:
                plan = parse_plan(text)
                compiled = compile_plan(plan)
                return {'plan':plan, 'compiled':compiled,
                        'planner':{'provider':c['provider'],'protocol':'dsh-headless' if c['provider']=='dsh' else c['protocol'],
                                   'model':c['model'] if c['provider']=='openai' else 'DSH · '+os.getenv('L2D_DSH_MODEL','deepseek-flash'),
                                   'attempts':attempt+1,'seconds':round(time.monotonic()-start,2)}}
            except (CompileError, PlannerError) as error:
                if attempt or 'unsupported' in text or 'refusal' in text:
                    raise PlannerError(str(error)) from None
                messages += [{'role':'assistant','content':text[:40000]},
                             {'role':'user','content':f'本地校验未通过：{error}。请修正并仅返回完整 JSON，不要改变用户意图。'}]
