"""Host-independent contract tests for the macOS port.

These run on any host and never touch a real VTube Studio install, the model,
or the login keychain: paths are resolved inside temporary trees, and the token
store is exercised with L2D_VTS_TOKEN_BACKEND=file.
"""
import os, stat, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import platform_support as ps
import vts_capture


def models_tree(root, layout):
    sub = {'windows': Path('VTube Studio_Data/StreamingAssets/Live2DModels'),
           'macos': Path('VTube Studio.app/Contents/Resources/Data/StreamingAssets/Live2DModels')}[layout]
    path = root / sub
    path.mkdir(parents=True, exist_ok=True)
    return path


class InstallLayoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_windows_layout_still_resolves(self):
        expected = models_tree(self.root, 'windows')
        self.assertEqual(ps.vts_models_dir(self.root), expected)

    def test_macos_bundle_layout_resolves(self):
        expected = models_tree(self.root, 'macos')
        self.assertEqual(ps.vts_models_dir(self.root), expected)
        # L2D_VTS_DIR may point at the install root or straight at the .app.
        self.assertEqual(ps.vts_models_dir(self.root / 'VTube Studio.app'), expected)

    def test_steam_bundle_without_space_resolves(self):
        # Steam ships "VTubeStudio.app"; the docs say "VTube Studio.app".
        expected = self.root / 'VTubeStudio.app/Contents/Resources/Data/StreamingAssets/Live2DModels'
        expected.mkdir(parents=True)
        self.assertEqual(ps.vts_models_dir(self.root), expected)
        self.assertEqual(ps.vts_models_dir(self.root / 'VTubeStudio.app'), expected)

    def test_missing_install_returns_none(self):
        self.assertIsNone(ps.vts_models_dir(self.root))

    def test_models_folder_wins_over_root(self):
        # A folder named Live2DModels inside the root must not shadow StreamingAssets.
        (self.root / 'Live2DModels').mkdir()
        expected = models_tree(self.root, 'windows')
        self.assertEqual(ps.vts_models_dir(self.root), expected)

    def test_library_folders_parses_escaped_paths(self):
        steam = self.root / 'Steam'
        (steam / 'steamapps').mkdir(parents=True)
        (steam / 'steamapps/libraryfolders.vdf').write_text(
            '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"C:\\\\Games\\\\Steam"\n\t}\n\t"1"\n\t{\n\t\t"path"\t\t"/Volumes/Games/Steam"\n\t}\n}\n',
            encoding='utf-8')
        folders = ps.library_folders(steam)
        self.assertIn(Path('/Volumes/Games/Steam'), folders)
        self.assertIn(Path('C:\\Games\\Steam'), folders)

    def test_find_vts_honours_override(self):
        expected = models_tree(self.root, 'macos')
        with patch.dict(os.environ, {'L2D_VTS_DIR': str(self.root)}):
            self.assertEqual(ps.vts_models_dir(ps.find_vts()), expected)

    def test_find_vts_reports_missing_install(self):
        # Hermetic: a real Steam library on this host must not satisfy the check.
        with patch.dict(os.environ, {'L2D_VTS_DIR': str(self.root)}), \
                patch.object(ps, 'steam_roots', return_value=[]):
            with self.assertRaises(ValueError) as caught:
                ps.find_vts()
        self.assertIn('VTube Studio', str(caught.exception))


class TokenStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'vts-token'
        self.env = patch.dict(os.environ, {'L2D_VTS_TOKEN_FILE': str(self.path),
                                           'L2D_VTS_TOKEN_BACKEND': 'file'})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_roundtrip_and_permissions(self):
        self.assertEqual(ps.save_token(b'token-abc'), 'file')
        self.assertEqual(ps.load_token(), b'token-abc')
        mode = stat.S_IMODE(self.path.stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_missing_token_returns_none(self):
        self.assertIsNone(ps.load_token())

    def test_empty_file_is_not_a_token(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(b'')
        self.assertIsNone(ps.load_token())

    def test_default_file_name_stays_windows_compatible(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('L2D_VTS_TOKEN_FILE', None)
            self.assertEqual(ps.token_path().name, 'vts-token.dpapi')

    def test_keychain_failure_falls_back_to_file(self):
        with patch.dict(os.environ, {'L2D_VTS_TOKEN_BACKEND': 'keychain'}):
            with patch.object(ps, '_keychain_store', side_effect=RuntimeError('denied')):
                self.assertEqual(ps.save_token(b'fallback'), 'file')
        self.assertEqual(self.path.read_bytes(), b'fallback')


class CaptureGuardTests(unittest.TestCase):
    def test_flags_are_zero_off_windows(self):
        if ps.IS_WINDOWS:
            self.assertEqual(ps.no_window_flags(), subprocess.CREATE_NO_WINDOW)
        else:
            self.assertEqual(ps.no_window_flags(), 0)

    def test_guard_explains_macos_alternatives(self):
        if ps.IS_WINDOWS:
            self.assertIsNone(vts_capture.require_spout())
            return
        with self.assertRaises(RuntimeError) as caught:
            vts_capture.require_spout()
        self.assertIn('Windows', str(caught.exception))
        self.assertIn('网页渲染', str(caught.exception))

    def test_probe_fails_before_touching_spoutgl(self):
        if ps.IS_WINDOWS:
            self.skipTest('Windows has a real Spout2 receiver')
        with self.assertRaises(RuntimeError):
            vts_capture.probe()

    def test_sender_selection_is_unchanged(self):
        self.assertEqual(vts_capture.choose_sender(['VTubeStudioSpout', 'OBS']), 'VTubeStudioSpout')
        with self.assertRaises(ValueError):
            vts_capture.choose_sender([])


class RuntimeResolutionTests(unittest.TestCase):
    def test_symlinked_venv_python_keeps_its_path(self):
        # Windows venv launchers are real copies, so the symlink trap is POSIX-only.
        if ps.IS_WINDOWS:
            self.skipTest('venv launchers are not symlinks on Windows')
        import runtime_tools
        with tempfile.TemporaryDirectory() as folder:
            link = Path(folder) / 'python3'
            try:
                link.symlink_to(sys.executable)
            except OSError:
                self.skipTest('this machine does not allow symlinks')
            with patch.dict(os.environ, {'PYTHON': str(link)}):
                self.assertEqual(runtime_tools.executable('python'), str(link))


class WindowsBranchTests(unittest.TestCase):
    """The Windows path must stay wired even when the tests run on macOS."""

    def test_dpapi_backend_roundtrip_through_forced_windows(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'vts-token.dpapi'
            fake = lambda data, decrypt=False: (b'enc:' + data) if not decrypt else data[4:]
            with patch.dict(os.environ, {'L2D_VTS_TOKEN_FILE': str(path)}), \
                    patch.object(ps, 'IS_WINDOWS', True), patch.object(ps, 'IS_MACOS', False), \
                    patch.object(ps, '_dpapi', side_effect=fake):
                self.assertEqual(ps.token_backend(), 'dpapi')
                self.assertEqual(ps.save_token(b'abc'), 'dpapi')
                self.assertEqual(path.read_bytes(), b'enc:abc')
                self.assertEqual(ps.load_token(), b'abc')

    def test_windows_debug_flag_is_preserved(self):
        self.assertEqual(ps.no_window_flags(), getattr(subprocess, 'CREATE_NO_WINDOW', 0))


if __name__ == '__main__':
    unittest.main()