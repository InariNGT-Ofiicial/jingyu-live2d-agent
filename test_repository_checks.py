"""Publication guard regressions; all tokens and files here are fabricated."""
from pathlib import Path
import tempfile
import unittest

from tools.check_public_tree import check_file, path_problem, secret_problems


class PublicTreeTests(unittest.TestCase):
    def test_private_assets_and_state_are_rejected(self):
        for name in ['model/skin.png', '.local/token.txt', 'foo/textures/0.png',
                     'runtime-config.json', 'A.MOC3', 'x.vtube.json', 'x.cdi3.json',
                     'web/vendor/live2dcubismcore.min.js', '.env.production',
                     'exports/a.json', 'performances/one-result.json', '../outside.py']:
            with self.subTest(name=name):
                self.assertIsNotNone(path_problem(name))

    def test_public_sources_and_examples_are_allowed(self):
        for name in ['core-inventory.json', 'runtime-config.example.json',
                     'tools/synthetic_model.py', 'licenses/SpoutGL-LICENSE.txt',
                     'web/vendor/pixi.min.js', '.github/workflows/checks.yml']:
            self.assertIsNone(path_problem(name), name)

    def test_obvious_tokens_are_detected_without_echoing_the_value(self):
        for token in ['ghp_' + 'A' * 36, 'github_pat_' + 'A' * 70,
                      'sk-proj-' + 'A' * 60, '-----BEGIN ' + 'OPENSSH PRIVATE KEY-----']:
            problems = secret_problems(token)
            self.assertTrue(problems)
            self.assertNotIn(token, str(problems))
        self.assertEqual(secret_problems('test-secret not-a-real-key sk-placeholder'), [])

    def test_json_nonfinite_and_malformed_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            file = root / 'example.json'
            for value in ['{"x":NaN}', '{broken']:
                file.write_text(value, encoding='utf-8')
                self.assertIn('invalid JSON', check_file(root, file.name))
            file.write_text('{"x":1}', encoding='utf-8')
            self.assertEqual(check_file(root, file.name), [])

    def test_binary_files_need_review(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'unknown.bin').write_bytes(b'\xff\xfe\x00')
            self.assertTrue(check_file(root, 'unknown.bin'))


if __name__ == '__main__':
    unittest.main()
