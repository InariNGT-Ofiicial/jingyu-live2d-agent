"""Package the current source snapshot and complete author model for local use."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from package_runtimes import bundle_core, bundle_voice, bundle_minecraft
LOCAL_FILES = {'.local/studio-voice.json','.local/minecraft/runtime.json',
               '.local/minecraft/world-server/server.properties','.local/minecraft/world-server/eula.txt'}


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-parent', type=Path,
                        help='Complete author directory containing DeepSeek and original notices/PSD')
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runtime-config', type=Path)
    parser.add_argument('--voice-config', type=Path)
    parser.add_argument('--bundle-electron', action='store_true', help='Include the installed Windows Electron runtime and its license notices')
    parser.add_argument('--bundle-runtimes', action='store_true', help='Include standalone Python, capture/MCP dependencies, Node and FFmpeg')
    parser.add_argument('--bundle-voice', action='store_true', help='Include the configured CosyVoice environment, weights and reference voice for local use')
    parser.add_argument('--bundle-minecraft', action='store_true', help='Include the installed test-server JRE, JAR and Node dependencies; no saved world')
    parser.add_argument('--stage-only', action='store_true', help='Prepare files for real smoke testing before creating the archive')
    parser.add_argument('--archive-stage', action='store_true', help='Seal a previously prepared stage after testing')
    args = parser.parse_args()
    stage = args.stage.resolve()
    if args.archive_stage:
        if args.output.exists():parser.error('Output already exists')
        seal(stage, args.output)
        return
    if stage.exists() or args.output.exists():
        parser.error('Stage and output must be new paths; existing releases are preserved')
    if not args.model_parent or not args.runtime_config:parser.error('--model-parent and --runtime-config are required')
    if args.bundle_voice and not args.voice_config:parser.error('--bundle-voice requires --voice-config')
    model = args.model_parent.resolve()
    if not (model / 'DeepSeek/大肥鱼.model3.json').is_file():
        parser.error('Model parent must contain DeepSeek/大肥鱼.model3.json')
    config = json.loads(args.runtime_config.read_text(encoding='utf-8-sig'))
    config = {k: v for k, v in config.items()
              if k in ('python', 'node', 'ffmpeg', 'ffprobe', 'capture_python')}
    python = config.get('python') or shutil.which('python')
    if not python or not Path(python).is_file():
        parser.error('A working Python path is required')
    config['python'] = python
    stage.mkdir(parents=True)
    suffixes = {'.py', '.mjs', '.json', '.txt', '.md', '.cmd', '.ps1', '.yml'}
    for source in ROOT.iterdir():
        if (source.is_file() and source.suffix in suffixes
                and source.name not in ('runtime-config.json', 'drawables-inventory.json')
                and not source.name.startswith('.')):
            shutil.copy2(source, stage / source.name)
    ignored = shutil.ignore_patterns('__pycache__', '*.pyc', '*-result.json', 'node_modules')
    for directory in ('docs', 'examples', 'licenses', 'performances', 'tools', 'web', 'desktop-pet', 'minecraft'):
        shutil.copytree(ROOT / directory, stage / directory, ignore=ignored)
    if args.bundle_electron:
        electron = ROOT / 'desktop-pet/node_modules/electron/dist'
        if not (electron / 'electron.exe').is_file():
            raise RuntimeError('Install desktop-pet Electron before bundling its runtime')
        shutil.copytree(electron, stage / 'runtime/electron')
        config['electron'] = 'runtime/electron/electron.exe'
        # Match the launcher port for users who invoke the packaged PowerShell entry directly.
        pet_launcher = stage / 'Start-Pet.ps1'
        pet_launcher.write_text(pet_launcher.read_text(encoding='utf-8').replace('[int]$Port=61944', '[int]$Port=61945'), encoding='utf-8-sig')
    # These contain a generated profile, not personal state, and are regenerated on startup.
    shutil.copytree(model, stage / 'model')
    if not (stage / 'web/vendor/live2dcubismcore.min.js').is_file():
        raise RuntimeError('Local full package requires the installed Cubism Core')
    bundled = {}
    if args.bundle_runtimes:
        print('Bundling standalone core runtimes...', flush=True)
        config, bundled = bundle_core(stage, config)
        python = str(stage/config['python'])
    if args.bundle_voice:
        print('Bundling offline CosyVoice environment and weights...', flush=True)
        bundled['voice'] = bundle_voice(stage, args.voice_config)
    if args.bundle_minecraft:
        print('Bundling Minecraft validation dependencies...', flush=True)
        bundled['minecraft'] = bundle_minecraft(ROOT, stage)
    write_json(stage / 'runtime-config.json', config)
    if args.voice_config and not args.bundle_voice:
        voice = json.loads(args.voice_config.read_text(encoding='utf-8-sig'))
        (stage / '.local').mkdir()
        write_json(stage / '.local/studio-voice.json', {'preset': voice['preset']})
    meta = json.loads((stage / 'beta.json').read_text(encoding='utf-8'))
    meta.update(modelBundled=True, distribution='local-full', port=61945,
                electronBundled=args.bundle_electron,
                runtimesBundled=bundled,
                sourceSnapshot='current working tree; file hashes in PACKAGE-MANIFEST.json')
    if args.bundle_electron:
        meta['externalDependencies'] = [v for v in meta.get('externalDependencies', []) if not v.startswith('Electron')]
    if args.bundle_runtimes:
        meta['distribution'] = 'local-integrated'
        meta['externalDependencies'] = [v for v in meta['externalDependencies'] if v not in ('Python','Node.js','FFmpeg')]
    if args.bundle_voice:
        meta['externalDependencies'] = [v for v in meta['externalDependencies'] if not v.startswith('CosyVoice')]
    write_json(stage / 'beta.json', meta)
    launcher = r'''@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONNOUSERSITE=1"
set "PATH=%~dp0runtime\ffmpeg;%~dp0runtime\node;%PATH%"
set "L2D_MODEL_DIR=%~dp0model\DeepSeek"
"PYTHON_PATH" launch.py --port 61945 %*
if errorlevel 1 pause
'''.replace('PYTHON_PATH', '%~dp0runtime\\python\\python.exe' if args.bundle_runtimes else python)
    (stage / 'Start-Local.cmd').write_bytes(launcher.replace('\n', '\r\n').encode('utf-8'))
    (stage / '本机包说明.txt').write_text(
        '鲸语 1.5.0 完整模型本机包\n\n'
        '解压到一个新目录，双击 Start-Local.cmd，入口 http://127.0.0.1:61945/。不要在 ZIP 内直接启动。\n'
        '包含全部当前源码、场景、交互贴图、完整原模型、PSD、原始作者说明和 Cubism Core。\n'
        '复用本机 Python、Node.js、FFmpeg、Spout 采集环境及 DS CosyVoice 预设路径；这些外部环境和模型权重不在 ZIP 中。\n' +
        ('网页桌宠不需要 VTS；本包已附带 Electron 及许可说明，解压后无需 npm 下载。支持完整触摸、袜口拖拽和全桌面鼠标注视。\n' if args.bundle_electron else '网页桌宠不需要 VTS；新目录先执行 npm install --prefix desktop-pet 安装 Electron。\n') +
        'VTS、OBS 功能仍需对应软件开启 API；新目录首次连接 VTS 需要授权。OBS 密码通过 JINGYU_OBS_PASSWORD 或 .local/obs-experiment-password 配置。\n'
        '迁移到其他电脑：按 README.md 安装依赖、修改 runtime-config.json 和语音预设路径，再用 Start-Beta.cmd。\n'
        '默认不含个人预设；升级自己的旧目录前备份 .local/presets.json，再复制到新包同名路径。不要覆盖旧目录。\n'
        '不含 API Key、OBS 密码、VTS / DSH 登录凭据、个人录制或任务历史。\n'
        '主舞台与场景实验、社区调试台、压力测试入口均保留。袜口实验仅支持网页，未接入 VTS / 离线交互导出。\n'
        '直播间 CLI / MCP 设置 JINGYU_STUDIO_URL=http://127.0.0.1:61945；bridge_cli.py 使用 --url 指定该地址。\n'
        '完整功能见 README.md、CHANGELOG.md 和 docs。原模型授权说明保留在 model；此包为本机交付，未上传公开仓库。\n',
        encoding='utf-8')
    if args.bundle_runtimes:
        (stage/'本机包说明.txt').write_text(
            '鲸语 1.5.0 · Windows x64 整合包（含完整模型）\n\n'
            '解压到新目录，建议 D:\\Jingyu-1.5，双击 Start-Local.cmd 或 Start-Beta.cmd。默认端口 61945。\n'
            '路径可以有空格；本地语音的 FST 库需要纯英文目录。不要在 ZIP 内启动。\n'
            '已附带完整模型/PSD/作者说明、Cubism Core、Python 3.12、Node、FFmpeg/ffprobe、Electron、Spout 采集/MCP 依赖。\n'
            + ('已附带独立 Python 3.10、CosyVoice2-0.5B 权重、DS 晓伊 A3 参考声线、离线文本前端和触摸音频。\n' if args.bundle_voice else '') +
            '预设播放、桌宠、触摸/服装交互、导出和本地语音无需另装上述依赖；自然语言云编排仍需自己的 API 或 DSH 登录。\n'
            'VTS 和 OBS 为可选独立应用，需要自行安装并开启 API；新机器首次 VTS 连接仍需授权。\n'
            + ('Minecraft 验证所需 Node 模块、JRE 与本地服务端已附带；首次启动建立新测试世界，不含旧存档。\n' if args.bundle_minecraft else 'Minecraft 可选验证项目需运行 tools/setup_minecraft.py 并安装 minecraft 的 npm 依赖。\n') +
            'IndexTTS 为研究工具，不是默认语音。\n'
            'Blender 不是播放直播间场景的依赖，重新建模才需要安装。\n'
            '本地 GPU 语音仍需兼容的显卡驱动；没有 CUDA 时使用 CPU，会较慢。\n'
            '已包含依赖的软件许可见 licenses/ 和 runtime 各组件目录，详细版本/哈希见 PACKAGE-MANIFEST.json。\n'
            '未包含 API Key、OBS 密码、VTS/DSH 凭据、旧录制、个人预设或 Minecraft 存档。\n'
            '个人升级请单独保留旧目录 .local/presets.json，勿覆盖旧包。\n'
            '这是本机使用整合包；模型作者说明与声线预设中的使用范围仍适用。GitHub 只同步源码。\n', encoding='utf-8')
    if args.bundle_electron:
        readme = stage / 'README.md'
        readme.write_text('> 本完整本机包已附带模型、Cubism Core 和 Electron。先阅读「本机包说明.txt」并运行 Start-Local.cmd；以下源码安装步骤无需重复执行。\n\n' + readme.read_text(encoding='utf-8'), encoding='utf-8')
        guide = stage / 'BETA-README.txt'
        guide.write_text(guide.read_text(encoding='utf-8').replace('两种包都不含个人日志、API Key、DSH/VTS 凭据和第三方可执行文件。', '本机包附带 Electron 桌宠运行时；不含个人日志、API Key 和 DSH/VTS 凭据。其他运行环境复用本机安装。'), encoding='utf-8')
    env = {k: v for k, v in os.environ.items() if k != 'L2D_MODEL_DIR'}
    env['PYTHONUTF8'] = '1'
    check = subprocess.run([python, str(stage / 'launch.py'), '--check'], cwd=stage,
                           env=env, capture_output=True, text=True, encoding='utf-8', check=True)
    print(check.stdout.strip(), flush=True)
    model_files = [p for p in model.rglob('*') if p.is_file()]
    for source in model_files:
        assert digest(source) == digest(stage / 'model' / source.relative_to(model)), source
    if args.stage_only:
        print(json.dumps({'stage':str(stage), 'startupCheck':'passed', 'modelHashes':'passed'}, ensure_ascii=True), flush=True)
        return
    seal(stage, args.output)


def seal(stage, output):
    meta = json.loads((stage/'beta.json').read_text(encoding='utf-8'))
    files = sorted(p for p in stage.rglob('*') if p.is_file() and '__pycache__' not in p.parts
                   and p.name != 'PACKAGE-MANIFEST.json'
                   and p.relative_to(stage).parts[0] not in ('logs','exports','evidence')
                   and (p.relative_to(stage).parts[0] != '.local' or p.relative_to(stage).as_posix() in LOCAL_FILES))
    for p in files:
        rel = p.relative_to(stage).as_posix()
        assert not rel.startswith('.local/') or rel in LOCAL_FILES, rel
        assert p.suffix != '.dpapi', rel
    print(f'Hashing {len(files)} files with 8 workers...', flush=True)
    def record(p):
        return {'path':p.relative_to(stage).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p)}
    records=[]
    with ThreadPoolExecutor(max_workers=8) as pool:
        for value in pool.map(record, files):
            records.append(value)
            if len(records)%10000==0:print(f'Hashed {len(records)}/{len(files)} files',flush=True)
    write_json(stage / 'PACKAGE-MANIFEST.json', {
        'version': meta['version'], 'distribution':meta['distribution'],
        'runtimes':meta.get('runtimesBundled',{}),
        'sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'modelFiles':sum(p.relative_to(stage).parts[0]=='model' for p in files),
        'files': records})
    files.append(stage / 'PACKAGE-MANIFEST.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    print('Hash manifest complete; compressing integrated package...', flush=True)
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED, compresslevel=3) as archive:
        for p in files:
            archive.write(p, 'Jingyu-1.5/' + p.relative_to(stage).as_posix())
    print('Checking ZIP CRC...', flush=True)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
    record = {'version': meta['version'], 'file': str(output.resolve()),
              'bytes': output.stat().st_size, 'sha256': digest(output),
              'files': len(files), 'modelFiles':sum(p.relative_to(stage).parts[0]=='model' for p in files),
              'startupCheck': 'passed', 'modelHashes': 'passed', 'zipCRC': 'passed'}
    write_json(output.with_suffix('.verification.json'), record)
    print(json.dumps(record, ensure_ascii=True), flush=True)


if __name__ == '__main__':
    main()
