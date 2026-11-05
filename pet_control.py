"""Launch the transparent web renderer, independently of VTS and Spout."""
import ctypes
import json
import os
import subprocess
import threading
import time

from model_profile import ROOT
from runtime_tools import executable

_lock = threading.Lock()


def _window(port):
    if os.name != 'nt':
        return None
    find = ctypes.windll.user32.FindWindowW
    find.restype = ctypes.c_void_p
    return find(None, f'鲸语 · 网页桌宠 · {port}')


def _state_file(port):
    return ROOT / '.local' / 'web-pet' / f'{port}.json'


def status(port=61944):
    hwnd = _window(port)
    running = bool(hwnd and ctypes.windll.user32.IsWindowVisible(ctypes.c_void_p(hwnd)))
    try:
        executable('electron')
        installed = True
    except ValueError:
        installed = False
    result = {'available': os.name == 'nt' and (installed or running), 'running': running,
              'renderer': 'web', 'requiresVts': False, 'sourceUrl': f'http://127.0.0.1:{port}/pet.html'}
    if not installed:
        result['error'] = '请先执行 npm install --prefix desktop-pet 安装网页桌宠运行时'
    if running:
        try:
            state = json.loads(_state_file(port).read_text(encoding='utf-8'))
            result.update({k: state[k] for k in ('ready', 'telemetry', 'clickThrough', 'bounds') if k in state})
        except (OSError, ValueError):
            pass
    return result


def switch(enabled, port=61944):
    if type(enabled) is not bool:
        raise ValueError('enabled 必须是布尔值')
    if os.name != 'nt':
        raise ValueError('透明网页桌宠目前支持 Windows')
    with _lock:
        hwnd = _window(port)
        if not enabled:
            if hwnd:
                ctypes.windll.user32.PostMessageW(ctypes.c_void_p(hwnd), 0x10, 0, 0)
                for _ in range(50):
                    if not _window(port):
                        break
                    time.sleep(.1)
                else:
                    raise ValueError('桌宠尚未退出，请稍后重试')
        elif not hwnd:
            runtime = executable('electron')
            log = ROOT / 'logs' / f'web-pet-{port}.log'
            log.parent.mkdir(exist_ok=True)
            _state_file(port).unlink(missing_ok=True)
            env = {k: v for k, v in os.environ.items() if k != 'ELECTRON_RUN_AS_NODE'}
            with log.open('w', encoding='utf-8') as errors:
                proc = subprocess.Popen([runtime, str(ROOT / 'desktop-pet'), '--url', f'http://127.0.0.1:{port}'],
                    cwd=ROOT, stdin=subprocess.DEVNULL, stdout=errors, stderr=errors,
                    env=env, creationflags=subprocess.CREATE_NO_WINDOW)
            for _ in range(225):
                if proc.poll() is not None:
                    detail = log.read_text(encoding='utf-8', errors='replace').strip().splitlines()
                    raise ValueError('网页桌宠启动失败：' + (detail[-1] if detail else '请检查 logs/' + log.name))
                current = status(port)
                if current['running'] and current.get('ready'):
                    return current
                time.sleep(.2)
            proc.terminate()
            raise ValueError('网页桌宠启动超时，请检查本机网页和模型资源；不需要 VTS')
        return status(port)
