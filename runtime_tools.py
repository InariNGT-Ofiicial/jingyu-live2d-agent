"""Resolve optional local runtimes without downloading executable files."""
import os,shutil,sys
from pathlib import Path
from model_profile import ROOT,read_json
def executable(name):
    config=read_json(ROOT/'runtime-config.json') if (ROOT/'runtime-config.json').exists() else {}
    candidates=[os.environ.get(name.upper()),config.get(name)]
    if name=='python':candidates.append(sys.executable)
    candidates.append(shutil.which(name))
    if name=='node':candidates.append(str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'))
    for p in candidates:
        if p and Path(p).is_file():return str(Path(p).resolve())
    raise ValueError(f'缺少 {name}；请设置 {name.upper()} 环境变量或 runtime-config.json')
