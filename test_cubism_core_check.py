import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from launch import cubism_core_check


class CubismCoreCheckTests(unittest.TestCase):
    def test_report_distinguishes_broken_files_from_an_unverified_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            core = root / 'web/vendor/live2dcubismcore.min.js'
            core.parent.mkdir(parents=True)
            reference = b'/* tested runtime */'
            expected = hashlib.sha256(reference).hexdigest()
            (root / 'vendor-sources.json').write_text(json.dumps([{'file': core.name, 'sha256': expected}]), encoding='utf-8')
            self.assertEqual(cubism_core_check(root)['status'], 'missing')
            for data, status in [(b'', 'invalid'), (b'\xef\xbb\xbf <!DOCTYPE html>', 'invalid'),
                                 (reference, 'verified'), (reference + b'\n', 'different')]:
                with self.subTest(status=status, data=data):
                    core.write_bytes(data)
                    result = cubism_core_check(root)
                    self.assertEqual(result['status'], status)
                    self.assertEqual(result['sha256'], hashlib.sha256(data).hexdigest())
                    self.assertEqual(result['expectedSha256'], expected)
