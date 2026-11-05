"""Copy installed, working Windows runtimes into a relocatable local release."""
import json
import os
from pathlib import Path
import shutil
import subprocess

IGNORE = shutil.ignore_patterns('__pycache__', '*.pyc', '.git', '.cache', '*.pdb')


def probe(python):
    code = 'import json,sys;print(json.dumps({"base":sys.base_prefix,"prefix":sys.prefix,"version":sys.version.split()[0]}))'
    return json.loads(subprocess.check_output([str(python), '-c', code], text=True))


def copy_tree(source, target):
    shutil.copytree(source, target, ignore=IGNORE, dirs_exist_ok=True)


def copy_python(python, target):
    info = probe(python)
    base, prefix = Path(info['base']), Path(info['prefix'])
    target.mkdir(parents=True)
    # A standalone interpreter, not a copied venv redirecting to the developer's machine.
    for path in base.iterdir():
        if path.is_file() and path.suffix.lower() in ('.exe', '.dll', '.zip', '.txt'):
            shutil.copy2(path, target/path.name)
    for name in ('DLLs', 'Lib', 'Library', 'tcl', 'share'):
        if (base/name).is_dir():copy_tree(base/name, target/name)
    if prefix != base:
        overlay = prefix/'Lib/site-packages'
        packages = target/'Lib/site-packages'
        # Replace each overlay package completely; don't mix two versions' native modules.
        for item in overlay.iterdir():
            if item.name == '__pycache__' or item.suffix == '.pyc':continue
            dest = packages/item.name
            if dest.is_dir():shutil.rmtree(dest)
            elif dest.exists():dest.unlink()
            if item.is_dir():copy_tree(item, dest)
            else:shutil.copy2(item, dest)
        overlay_metadata = {p.name.split('-')[0].lower() for p in overlay.glob('*.dist-info')}
        for item in packages.glob('*.dist-info'):
            if item.name.split('-')[0].lower() in overlay_metadata and not (overlay/item.name).exists():
                shutil.rmtree(item)
    # Isolate from global/user packages and developer PYTHONPATH. site still loads wheel .pth files.
    version = ''.join(info['version'].split('.')[:2])
    (target/f'python{version}._pth').write_text('Lib\nDLLs\nLib\\site-packages\n.\n..\\..\nimport site\n', encoding='ascii')
    return info['version']


def bundle_core(stage, config):
    capture = config.get('capture_python') or config['python']
    version = copy_python(capture, stage/'runtime/python')
    result = {'python': 'runtime/python/python.exe', 'capture_python': 'runtime/python/python.exe'}
    for key, folder in [('node', 'node'), ('ffmpeg', 'ffmpeg'), ('ffprobe', 'ffmpeg')]:
        source = Path(config.get(key) or shutil.which(key) or '')
        if not source.is_file():raise ValueError(f'Configure an installed {key} in runtime-config.json')
        target = stage/'runtime'/folder/source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        result[key] = target.relative_to(stage).as_posix()
        if key == 'node' and (source.parent/'node_modules/npm').is_dir():
            copy_tree(source.parent/'node_modules/npm', target.parent/'node_modules/npm')
            for name in ('npm','npm.cmd','npx','npx.cmd'):
                if (source.parent/name).is_file():shutil.copy2(source.parent/name,target.parent/name)
    if config.get('electron'):result['electron'] = config['electron']
    return result, {'python': version, 'capture': True, 'mcp': True, 'node': True, 'ffmpeg': True}


def bundle_voice(stage, voice_config):
    from studio_voice import load_preset
    cfg = json.loads(voice_config.read_text(encoding='utf-8-sig'))
    preset_file = Path(cfg['preset'])
    if not preset_file.is_absolute():preset_file = voice_config.parent.parent/preset_file
    preset = load_preset(preset_file)
    engine = preset['engine']
    project = Path(engine['project'])
    version = copy_python(engine['python'], stage/'runtime/voice-python')
    target = stage/'voice'
    source = project/'CosyVoice_源码'
    for name in ('cosyvoice', 'third_party'):
        copy_tree(source/name, target/'CosyVoice_源码'/name)
    for name in ('LICENSE', 'README.md', 'requirements.txt'):
        shutil.copy2(source/name, target/'CosyVoice_源码'/name)
    copy_tree(Path(engine['model_dir']), target/'CosyVoice_源码/pretrained_models/CosyVoice2-0.5B')
    shutil.copy2(project/'wetext_local_patch.py', target/'wetext_local_patch.py')
    wetext = Path(os.environ.get('WETEXT_MODELS_DIR', str(project.parent/'wetext_models')))
    copy_tree(wetext, target/'wetext_models')
    ref = preset_file.parent/preset['reference']['file']
    shutil.copy2(ref, target/'reference.wav')
    preset['engine'].update(python='../runtime/voice-python/python.exe', project='.',
                           model_dir='CosyVoice_源码/pretrained_models/CosyVoice2-0.5B')
    preset['reference']['file'] = 'reference.wav'
    preset['reference'].pop('source_paths', None)
    for name in ('source_workspace', 'source_preset', 'samples'):preset.pop(name, None)
    (target/'preset.json').write_text(json.dumps(preset, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (stage/'.local').mkdir(exist_ok=True)
    (stage/'.local/studio-voice.json').write_text('{"preset": "voice/preset.json"}\n', encoding='utf-8')
    return {'python': version, 'engine': engine['name'], 'preset': preset['id'], 'offlineModels': True}


def bundle_minecraft(root, stage):
    local=root/'.local/minecraft'
    cfg=json.loads((local/'runtime.json').read_text(encoding='utf-8'))
    copy_tree(root/'minecraft/node_modules',stage/'minecraft/node_modules')
    copy_tree(Path(cfg['java']).parents[1],stage/'runtime/java')
    (stage/'runtime/minecraft').mkdir()
    shutil.copy2(cfg['jar'],stage/'runtime/minecraft/server.jar')
    world=stage/'.local/minecraft/world-server'
    world.mkdir(parents=True)
    # Preserve the accepted local server settings, never the old world or players.
    for name in ('server.properties','eula.txt'):shutil.copy2(Path(cfg['cwd'])/name,world/name)
    cfg.update(java='runtime/java/bin/java.exe',jar='runtime/minecraft/server.jar',cwd='.local/minecraft/world-server')
    (world.parent/'runtime.json').write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf-8')
    return {'version':cfg['version'],'freshWorld':True,'nodeModules':True,'java':True}
