"""Run public contract tests in a disposable copy, without personal state."""
import argparse
import compileall
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from synthetic_model import create_model

ROOT = Path(__file__).resolve().parents[1]


def run(command, stage, env):
    print('+ ' + ' '.join(map(str, command)), flush=True)
    subprocess.run(command, cwd=stage, env=env, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', default=shutil.which('node'), help='Node.js executable')
    args = parser.parse_args()
    if not args.node:
        parser.error('Node.js is required; put it on PATH or pass --node')
    node = str(Path(shutil.which(args.node) or args.node).resolve())
    try:
        import PIL  # noqa: F401 -- missing Pillow must fail, not skip recorder tests.
        import websocket  # noqa: F401 -- imported by mocked deployment tests.
    except ImportError:
        parser.error('Install requirements-test.txt with this Python interpreter first')
    # Copy only public source inputs. Never copy .local, runtime-config, model,
    # Cubism Core, credentials, logs, exports, or an existing generated profile.
    scratch = ROOT / '.local' / 'checks'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='run-', dir=scratch) as folder:
        stage = Path(folder)
        paths = [*ROOT.glob('*.py'), *ROOT.glob('*.mjs'), ROOT / 'core-inventory.json',
                 ROOT / 'dsh-planner.patch.yml', ROOT / 'renderer-patch.json',
                 ROOT / 'web/vendor/cubism4.min.js', ROOT / 'web/vendor/cubism4.colors.min.js',
                 *ROOT.glob('performances/*.json'),
                 *ROOT.glob('web/*.mjs'), *ROOT.glob('tools/*.py')]
        for source in paths:
            target = stage / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        model = create_model(stage)
        temp = stage / '.local' / 'tmp'
        temp.mkdir(parents=True)
        env = {key: value for key, value in os.environ.items()
               if not key.upper().startswith(('L2D_', 'OPENAI_', 'DSH_', 'VTS_'))}
        env.update(L2D_MODEL_DIR=str(model), L2D_LLM_PROVIDER='openai',
                   PYTHONUTF8='1', PYTHONIOENCODING='utf-8',
                   TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp))
        print('Synthetic contracts only; no real model, VTS, GPU or service is used.', flush=True)
        if not compileall.compile_dir(stage, quiet=1):
            raise SystemExit('Python syntax check failed')
        run([sys.executable, '-c', 'from model_profile import write_profile; write_profile()'], stage, env)
        run([sys.executable, '-m', 'unittest', 'discover', '-s', '.', '-p', 'test_*.py', '-v'], stage, env)
        for path in sorted([*stage.glob('*.mjs'), *stage.glob('web/*.mjs')]):
            run([node, '--check', str(path.relative_to(stage))], stage, env)
        tests = sorted(stage.glob('test_*.mjs'))
        if not tests:
            raise SystemExit('No Node tests found')
        for path in tests:
            run([node, path.name], stage, env)
        print('Public contract checks passed. Hardware/visual regression remains manual.', flush=True)


if __name__ == '__main__':
    main()
