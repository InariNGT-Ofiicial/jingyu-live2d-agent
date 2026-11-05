"""Resolve optional local runtimes without downloading executable files."""
import os,shutil,sys
from pathlib import Path
from model_profile import ROOT,read_json
def executable(name):
    config=read_json(ROOT/'runtime-config.json') if (ROOT/'runtime-config.json').exists() else {}
    candidates=[os.environ.get(name.upper()),config.get(name)]
    if name=='capture_python':
        candidates += [str(ROOT/'.local/vts-capture/Scripts/python.exe'),sys.executable]
    if name=='python':candidates.append(sys.executable)
    if name=='electron':candidates += [str(ROOT/'runtime/electron/electron.exe'),str(ROOT/'desktop-pet/node_modules/electron/dist/electron.exe')]
    candidates.append(shutil.which(name))
    if name=='node':candidates.append(str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'))
    for p in candidates:
        if p:
            path=Path(p)
            if not path.is_absolute():path=ROOT/path
            if path.is_file():return str(path.resolve())
    raise ValueError(f'缺少 {name}；请设置 {name.upper()} 环境变量或 runtime-config.json')
