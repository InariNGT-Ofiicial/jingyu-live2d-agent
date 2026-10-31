"""Resolve optional local runtimes without downloading executable files."""
import os,shutil,sys
from pathlib import Path
from model_profile import ROOT,read_json
from platform_support import IS_WINDOWS
POSIX_BINS=['/opt/homebrew/bin','/usr/local/bin','/usr/bin']

def _absolute(p):
    # Never resolve symlinks here: a venv's bin/python is a symlink to the base
    # interpreter, and resolving it drops that venv's site-packages.
    path=Path(p).expanduser()
    return path if path.is_absolute() else path.absolute()

def executable(name):
    config=read_json(ROOT/'runtime-config.json') if (ROOT/'runtime-config.json').exists() else {}
    candidates=[os.environ.get(name.upper()),config.get(name)]
    if name=='capture_python':
        # Windows venv layout, then the POSIX one, then this interpreter.
        candidates += [str(ROOT/'.local/vts-capture/Scripts/python.exe'),str(ROOT/'.local/vts-capture/bin/python'),sys.executable]
    if name=='python':candidates.append(sys.executable)
    candidates.append(shutil.which(name))
    if name=='node':candidates.append(str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'))
    if not IS_WINDOWS:candidates += [str(Path(base)/name) for base in POSIX_BINS]
    for p in candidates:
        if p and _absolute(p).is_file():return str(_absolute(p))
    hint=f'请设置 {name.upper()} 环境变量或 runtime-config.json'
    if not IS_WINDOWS:hint+='；也可用 Homebrew 安装（brew install '+{'ffmpeg':'ffmpeg','node':'node'}.get(name,name)+'）'
    raise ValueError(f'缺少 {name}；'+hint)