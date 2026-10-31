"""Check public Git files for excluded assets, private state and obvious secrets.

This is a narrow guard, not a complete secret detector or a license audit.
Diagnostics name the file and rule, never the matching credential or line text.
"""
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DIRS = {'.local', '.venv', 'venv', 'node_modules', 'model', 'textures',
                'logs', 'exports', 'evidence', 'research', 'stress', 'work', '__pycache__'}
PRIVATE_FILES = {'runtime-config.json', 'presets.json', 'planner-settings.json',
                 'model-profile.json', 'stress-catalog.json', 'drawables-inventory.json'}
PRIVATE_SUFFIXES = ('.moc3', '.psd', '.model3.json', '.physics3.json', '.exp3.json',
                    '.motion3.json', '.cdi3.json', '.vtube.json', '.dpapi', '.pyc',
                    '.zip', '.mp4', '.gif', '.webm')
SECRET_PATTERNS = {
    'private key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    'GitHub token': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})\b'),
    'API token': re.compile(r'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}\b'),
}


def path_problem(name):
    path = PurePosixPath(name.lower())
    if path.is_absolute() or '..' in path.parts:
        return 'path outside repository'
    if set(path.parts[:-1]) & PRIVATE_DIRS:
        return 'private/generated directory'
    if (path.name in PRIVATE_FILES or path.name.startswith('.env')
            or path.name.startswith('live2dcubismcore')
            or path.name.endswith(PRIVATE_SUFFIXES) or path.name.endswith('-result.json')):
        return 'private/generated/proprietary file'
    return None


def secret_problems(content):
    return [name for name, pattern in SECRET_PATTERNS.items() if pattern.search(content)]


def reject_constant(value):
    raise ValueError('non-finite JSON number')


def check_file(root, name):
    problem = path_problem(name)
    if problem:
        return [problem]
    path = root / name
    if path.is_symlink():
        return ['symlinks require manual review']
    if not path.exists():  # A tracked file deleted in the working tree.
        return []
    if root.resolve() not in path.resolve().parents:
        return ['path outside repository']
    try:
        content = path.read_text(encoding='utf-8-sig')
    except UnicodeDecodeError:
        return ['binary/non-UTF-8 file requires manual review']
    problems = secret_problems(content)
    if path.suffix.lower() == '.json':
        try:
            json.loads(content, parse_constant=reject_constant)
        except (ValueError, TypeError):
            problems.append('invalid JSON')
    return problems


def main():
    result = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
                            cwd=ROOT, check=True, capture_output=True)
    names = sorted(set(result.stdout.decode('utf-8').split('\0')) - {''})
    failures = [(name, problem) for name in names for problem in check_file(ROOT, name)]
    for name, problem in failures:
        print(f'{name}: {problem}')
    if failures:
        raise SystemExit(1)
    print(f'Public tree: {len(names)} files checked; no excluded paths, invalid JSON or obvious tokens found.')


if __name__ == '__main__':
    main()
