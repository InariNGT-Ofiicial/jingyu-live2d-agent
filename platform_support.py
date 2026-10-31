"""Host facts the local bridge needs: install paths, token vault, subprocess flags.

Windows keeps the original behaviour (Steam registry, DPAPI, Spout2 capture).
macOS resolves Steam under Application Support and stores the VTS token in the
login keychain, falling back to a 0600 file when the keychain is unavailable.
Everything else falls back to the file store. Native Spout2 capture stays
Windows-only by upstream design; nothing here pretends otherwise.
"""
import os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IS_WINDOWS = sys.platform.startswith('win')
IS_MACOS = sys.platform == 'darwin'
IS_LINUX = sys.platform.startswith('linux')

CAPTURE_UNAVAILABLE = ('Spout2 原生采集仅 Windows 可用：macOS 请在 VTS 开启 NDI 后用 OBS 录制，'
                       '或直接把导出源设为网页渲染（renderer=web）')


def platform_name():
    return 'windows' if IS_WINDOWS else 'macos' if IS_MACOS else sys.platform


def no_window_flags():
    """CREATE_NO_WINDOW on Windows; POSIX rejects a non-zero creationflags."""
    return getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def capture_available():
    return IS_WINDOWS


# --- Steam and VTube Studio ------------------------------------------------

def steam_roots():
    """Steam client roots that exist on this host, most specific first."""
    roots = []
    if IS_WINDOWS:
        roots.append(Path(os.getenv('ProgramFiles(x86)', 'C:/Program Files (x86)')) / 'Steam')
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as key:
                roots.insert(0, Path(winreg.QueryValueEx(key, 'SteamPath')[0]))
        except (ImportError, OSError):
            pass
    elif IS_MACOS:
        roots.append(Path.home() / 'Library' / 'Application Support' / 'Steam')
    else:
        roots += [Path.home() / '.local/share/Steam', Path.home() / '.steam/steam']
    return [p for p in roots if p.is_dir()]


def library_folders(steam_root):
    """Extra Steam libraries listed in steamapps/libraryfolders.vdf."""
    vdf = Path(steam_root) / 'steamapps' / 'libraryfolders.vdf'
    if not vdf.is_file():
        return []
    text = vdf.read_text(encoding='utf-8', errors='replace')
    # Steam escapes backslashes in the VDF no matter which host wrote it.
    return [Path(x.replace('\\\\', '\\')) for x in re.findall(r'"path"\s+"([^"]+)"', text)]


def vts_models_dir(root):
    """`.../StreamingAssets/Live2DModels` for a VTS install root or .app bundle."""
    root = Path(root)
    bases = [root]
    if root.suffix == '.app':
        bases.insert(0, root / 'Contents' / 'Resources' / 'Data')
    bases += [root / 'VTube Studio_Data', root / 'Contents' / 'Resources' / 'Data']
    # macOS bundle names vary in practice ("VTube Studio.app" in the docs,
    # "VTubeStudio.app" as shipped by Steam), so probe every bundle on disk.
    try:
        bundles = sorted(p for p in root.iterdir() if p.suffix == '.app' and p.is_dir())
    except OSError:
        bundles = []
    bases += [bundle / 'Contents' / 'Resources' / 'Data' for bundle in bundles]
    for base in bases:
        candidate = base / 'StreamingAssets' / 'Live2DModels'
        if candidate.is_dir():
            return candidate
    return None


def find_vts():
    roots = []
    if os.getenv('L2D_VTS_DIR'):
        roots.append(Path(os.environ['L2D_VTS_DIR']))
    steam = steam_roots()
    libraries = list(steam) + [p for s in steam for p in library_folders(s)]
    roots += [p / 'steamapps' / 'common' / 'VTube Studio' for p in libraries]
    for candidate in roots:
        if vts_models_dir(candidate):
            return Path(candidate)
    hint = ('请通过 Steam 安装 VTube Studio，或把 L2D_VTS_DIR 指向 VTube Studio.app 或安装目录'
            if IS_MACOS else '请安装或设置 L2D_VTS_DIR 为其安装目录')
    raise ValueError('未找到 VTube Studio；' + hint)


# --- VTS plugin token ------------------------------------------------------

KEYCHAIN_SERVICE = 'Jingyu Motion Bridge'
KEYCHAIN_ACCOUNT = 'jingyu-vts-token'


def token_path():
    return Path(os.getenv('L2D_VTS_TOKEN_FILE') or ROOT / '.local' / 'vts-token.dpapi')


def token_backend():
    """`L2D_VTS_TOKEN_BACKEND` forces file or keychain; default is native."""
    forced = (os.getenv('L2D_VTS_TOKEN_BACKEND') or '').strip().lower()
    if forced in ('file', 'keychain'):
        return forced
    return 'keychain' if IS_MACOS else 'dpapi' if IS_WINDOWS else 'file'


def _dpapi(data, decrypt=False):
    import ctypes

    class Blob(ctypes.Structure):
        _fields_ = [('size', ctypes.c_ulong), ('data', ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data)
    src = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out = Blob()
    fn = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    if not fn(ctypes.byref(src), None, None, None, None, 1, ctypes.byref(out)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out.data, out.size)
    finally:
        ctypes.windll.kernel32.LocalFree(out.data)


def _security(args, timeout=10):
    return subprocess.run(['security', *args], capture_output=True, text=True, timeout=timeout)


def _keychain_store(token):
    # The token appears in argv for the lifetime of the call; VTS tokens are
    # local plugin grants, and `security` offers no stdin path for -w.
    result = _security(['add-generic-password', '-a', KEYCHAIN_ACCOUNT, '-s', KEYCHAIN_SERVICE,
                        '-w', token.decode('utf-8'), '-U'])
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'keychain write failed')


def _keychain_load():
    result = _security(['find-generic-password', '-a', KEYCHAIN_ACCOUNT, '-s', KEYCHAIN_SERVICE, '-w'])
    if result.returncode:
        return None
    value = result.stdout.strip()
    return value.encode('utf-8') if value else None


def save_token(token):
    """Persist the VTS authentication token with the strongest local vault."""
    if isinstance(token, str):
        token = token.encode('utf-8')
    backend = token_backend()
    if backend == 'keychain':
        try:
            _keychain_store(token)
            if token_path().exists():
                token_path().unlink()
            return 'keychain'
        except Exception as error:
            print(f'提示：钥匙串写入失败（{error}），改用 0600 权限文件。', file=sys.stderr)
            backend = 'file'
    path = token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _dpapi(token) if backend == 'dpapi' else token
    path.write_bytes(payload)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return backend


def load_token():
    """Return the stored token bytes, or None when nothing usable is stored."""
    backend = token_backend()
    if backend == 'keychain':
        try:
            token = _keychain_load()
            if token:
                return token
        except Exception:
            pass
    path = token_path()
    if not path.is_file():
        return None
    raw = path.read_bytes()
    if not raw:
        return None
    # Windows keeps the original DPAPI blob at the original .dpapi path.
    if backend == 'dpapi':
        return _dpapi(raw, decrypt=True)
    return raw


def clear_token():
    path = token_path()
    if path.exists():
        path.unlink()
    if token_backend() == 'keychain':
        try:
            _security(['delete-generic-password', '-a', KEYCHAIN_ACCOUNT, '-s', KEYCHAIN_SERVICE])
        except Exception:
            pass