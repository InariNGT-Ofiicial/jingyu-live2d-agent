import json
import shutil
import tempfile
import unittest
from pathlib import Path
import patch_renderer as pr

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT/'web/vendor/cubism4.min.js'
OUTPUT = ROOT/'web/vendor/cubism4.colors.min.js'
MANIFEST = ROOT/'renderer-patch.json'


class RendererPatchTests(unittest.TestCase):
    def setUp(self):
        self.raw = SOURCE.read_bytes()
        self.payload, self.record = pr.build(self.raw)

    def test_manifest_is_regenerated_from_the_vendor_source(self):
        self.assertEqual(json.loads(MANIFEST.read_bytes().decode('utf-8')), self.record)

    def test_digests_follow_git_bytes_not_the_checkout(self):
        # Git stores text as LF. Both digests must stay stable on a CRLF checkout
        # (core.autocrlf=true) instead of recording local line endings.
        self.assertEqual(pr.sha256(pr.to_lf(self.raw)), self.record['sourceSHA256'])
        self.assertEqual(pr.sha256(pr.to_lf(OUTPUT.read_bytes())), self.record['patchedSHA256'])
        self.assertNotIn(b'\r', self.payload)

    def test_line_endings_do_not_change_the_generated_files(self):
        lf = pr.to_lf(self.raw)
        crlf = lf.replace(b'\n', b'\r\n')
        self.assertNotEqual(lf, crlf)
        self.assertEqual(pr.build(crlf), pr.build(lf))
        self.assertEqual(pr.build(crlf)[1], self.record)

    def test_clipping_mask_buffer_is_raised(self):
        text = self.payload.decode('utf-8')
        self.assertEqual(text.count(f'this._clippingMaskBufferSize={pr.CLIPPING_MASK_BUFFER_SIZE}'), 1)
        self.assertNotIn('this._clippingMaskBufferSize=256', text)

    def test_rerun_rewrites_identical_files(self):
        with tempfile.TemporaryDirectory() as folder:
            stage = Path(folder)
            (stage/'web/vendor').mkdir(parents=True)
            shutil.copyfile(SOURCE, stage/'web/vendor/cubism4.min.js')
            self.assertEqual(len(pr.write_outputs(stage, *pr.build((stage/'web/vendor/cubism4.min.js').read_bytes()))), 2)
            first = ((stage/'web/vendor/cubism4.colors.min.js').read_bytes(),
                     (stage/'renderer-patch.json').read_bytes())
            self.assertEqual(pr.write_outputs(stage, *pr.build((stage/'web/vendor/cubism4.min.js').read_bytes())), [])
            second = ((stage/'web/vendor/cubism4.colors.min.js').read_bytes(),
                      (stage/'renderer-patch.json').read_bytes())
            self.assertEqual(first, second)
            self.assertEqual(first[0], self.payload)
            self.assertEqual(json.loads(first[1].decode('utf-8')), self.record)


if __name__ == '__main__':
    unittest.main()
