"""Create or reuse an intact author-model copy; no manual parameter mapping."""
import hashlib, json, os, shutil
from pathlib import Path
from model_profile import ROOT, MODEL_ROOT, read_json
from platform_support import find_vts, vts_models_dir


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def live2d_models():
    """The Live2DModels folder inside the detected VTube Studio install."""
    return vts_models_dir(find_vts())


def ensure_import():
    manifest = ROOT / 'research/vts-comparison/import-manifest.json'
    if manifest.is_file():
        old = read_json(manifest)
        if Path(old.get('destination', '')).is_dir():
            return old
    dest = live2d_models() / 'Jingyu-Author-Comparison'
    mid = read_json(MODEL_ROOT / '大肥鱼.vtube.json')['ModelID']
    if dest.exists():
        if not (dest / '大肥鱼.vtube.json').is_file() or read_json(dest / '大肥鱼.vtube.json')['ModelID'] != mid or sha(dest / '大肥鱼.moc3') != sha(MODEL_ROOT / '大肥鱼.moc3') or sha(dest / '大肥鱼.physics3.json') != sha(MODEL_ROOT / '大肥鱼.physics3.json'):
            raise ValueError('VTS 专用目录已有不同模型，未覆盖；请改名后重新初始化')
    else:
        if dest.resolve() == MODEL_ROOT.resolve() or MODEL_ROOT.resolve() in dest.resolve().parents:
            raise ValueError('不能写入原模型目录')
        shutil.copytree(MODEL_ROOT, dest)
    result = {'source': str(MODEL_ROOT), 'destination': str(dest), 'modelID': mid, 'sourceConfigSha256': sha(MODEL_ROOT / '大肥鱼.vtube.json'), 'physicsSha256': sha(MODEL_ROOT / '大肥鱼.physics3.json'), 'method': 'reuse matching copy or copy complete author model; native hotkey installed on first execution'}
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    print(json.dumps(ensure_import(), ensure_ascii=True, indent=2))