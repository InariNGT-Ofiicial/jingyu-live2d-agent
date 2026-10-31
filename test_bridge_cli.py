"""Exercise the real CLI entrypoint with mocked HTTP; no bridge or VTS is used."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent
BASE = 'http://127.0.0.1:61959'


class Console(io.StringIO):
    def reconfigure(self, **kwargs):
        pass


class CliTests(unittest.TestCase):
    def invoke(self, args, responses=(), clock=None):
        stdout, stderr, requests = Console(), Console(), []
        replies = iter(responses)

        def open_request(req, timeout):
            requests.append(req)
            value = next(replies)  # Unexpected extra requests fail the test.
            if isinstance(value, Exception):
                raise value
            return io.BytesIO(json.dumps(value).encode('utf-8'))

        with patch.object(sys, 'argv', ['bridge_cli.py', *args]), \
                patch('urllib.request.urlopen', side_effect=open_request), \
                patch('time.sleep'), patch('time.monotonic', side_effect=clock), \
                patch.dict(sys.modules, {'run_vts_comparison': None}), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                runpy.run_path(str(ROOT / 'bridge_cli.py'), run_name='__main__')
                code = 0
            except SystemExit as error:
                code = error.code
        return code, stdout.getvalue(), stderr.getvalue(), requests

    def test_legacy_command_submits_canonical_plan_and_waits_for_its_own_job(self):
        code, out, err, requests = self.invoke(
            ['vts-perform', '15', '--url', BASE, '--request-id', 'inbox-7'],
            [{'id': 'our-job', 'status': 'queued'},
             {'jobs': [{'id': 'other-job', 'status': 'completed'},
                       {'id': 'our-job', 'status': 'deploying'}]},
             {'jobs': [{'id': 'our-job', 'status': 'playing'}]},
             {'jobs': [{'id': 'our-job', 'status': 'completed', 'progress': 1}]}],
            clock=[0, 1, 2, 3])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)['status'], 'completed')
        self.assertEqual(json.loads(err)['status'], 'queued')
        self.assertEqual([r.full_url for r in requests],
                         [BASE + '/api/execute', *[BASE + '/api/state'] * 3])
        payload = json.loads(requests[0].data)
        self.assertEqual(payload, {
            'plan': json.loads((ROOT / 'performances/15-flirt-layered.json').read_text(encoding='utf-8')),
            'backend': 'vts', 'requestId': 'inbox-7'})

    def test_output_saves_the_terminal_receipt(self):
        scratch = ROOT / '.local/tests'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as folder:
            output = Path(folder) / 'nested' / 'receipt.json'
            receipt = {'id': 'job', 'status': 'completed', 'backend': 'vts'}
            code, out, _, requests = self.invoke(
                ['vts-perform', '15', '--url', BASE, '--output', str(output), '--wait'],
                [receipt], clock=[0])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out), receipt)
            self.assertEqual(json.loads(output.read_text(encoding='utf-8')), receipt)
            self.assertEqual(len(requests), 1)

    def test_invalid_legacy_selection_and_conflicting_options_never_submit(self):
        for args in [['vts-perform'], ['vts-perform', '14'],
                     ['vts-perform', '15', '--backend', 'web'],
                     ['vts-perform', '15', '--port', '8001']]:
            with self.subTest(args=args):
                code, _, err, requests = self.invoke(args)
                self.assertEqual(code, 2)
                self.assertIn('error:', err)
                self.assertEqual(requests, [])

    def test_error_and_interruption_are_failure_exit_codes(self):
        for status in ['error', 'interrupted']:
            with self.subTest(status=status):
                code, out, _, _ = self.invoke(
                    ['vts-perform', '15', '--url', BASE],
                    [{'id': 'job', 'status': 'queued'},
                     {'jobs': [{'id': 'job', 'status': status}]}], clock=[0, 1])
                self.assertEqual(code, 1)
                self.assertEqual(json.loads(out)['status'], status)

    def test_timeout_does_not_stop_or_resubmit_a_job(self):
        code, _, _, requests = self.invoke(
            ['vts-perform', '15', '--url', BASE],
            [{'id': 'job', 'status': 'queued'}], clock=[0, 181])
        self.assertIsInstance(code, str)
        self.assertIn('超时', code)
        self.assertEqual(len(requests), 1)

    def test_missing_job_reports_an_actionable_error(self):
        code, _, _, requests = self.invoke(
            ['vts-perform', '15', '--url', BASE],
            [{'id': 'job', 'status': 'queued'}, {'jobs': []}], clock=[0, 1])
        self.assertIsInstance(code, str)
        self.assertIn('job', code)
        self.assertIn('state', code)
        self.assertEqual(len(requests), 2)

    def test_http_rejection_does_not_poll_or_retry(self):
        rejection = HTTPError(BASE + '/api/execute', 400, 'busy', {},
                              io.BytesIO(b'{"error":"busy"}'))
        self.addCleanup(rejection.close)
        code, _, _, requests = self.invoke(
            ['vts-perform', '15', '--url', BASE], [rejection])
        self.assertEqual(code, '{"error":"busy"}')
        self.assertEqual(len(requests), 1)

    def test_missing_bridge_reports_how_to_connect(self):
        code, _, _, requests = self.invoke(
            ['vts-perform', '15', '--url', BASE], [URLError('connection refused')])
        self.assertIsInstance(code, str)
        self.assertIn('--url', code)
        self.assertIn('启动', code)
        self.assertEqual(len(requests), 1)

    def test_direct_vts_status_keeps_its_default_and_explicit_port(self):
        for args, port in [([], 8001), (['--port', '8123'], 8123)]:
            with self.subTest(port=port):
                client = Mock()
                client.call.return_value = {}
                factory = Mock(return_value=client)
                with patch.dict(sys.modules, {'vts_client': SimpleNamespace(VTS=factory)}):
                    code, _, _, requests = self.invoke(['vts-status', *args])
                self.assertEqual(code, 0)
                factory.assert_called_once_with(port)
                client.close.assert_called_once()
                self.assertEqual(requests, [])

    def test_direct_vts_stream_keeps_its_default_and_explicit_port(self):
        scratch = ROOT / '.local/tests'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as folder:
            output = Path(folder) / 'trace.json'
            for args, port in [([], 8001), (['--port', '8123'], 8123)]:
                with self.subTest(port=port):
                    play = Mock(return_value={'samples': [], 'status': 'completed'})
                    with patch.dict(sys.modules, {'vts_tracking': SimpleNamespace(play=play)}):
                        code, _, _, requests = self.invoke([
                            'vts-stream', str(ROOT / 'performances/15-flirt-layered.json'),
                            '--output', str(output), *args])
                    self.assertEqual(code, 0)
                    self.assertEqual(play.call_args.args[1], port)
                    self.assertIn('samples', json.loads(output.read_text(encoding='utf-8')))
                    self.assertEqual(requests, [])

    def test_execute_wait_uses_the_same_receipt_and_failure_rules(self):
        for status, expected in [('completed', 0), ('error', 1), ('interrupted', 1)]:
            with self.subTest(status=status):
                code, out, _, requests = self.invoke(
                    ['execute', str(ROOT / 'performances/15-flirt-layered.json'),
                     '--backend', 'vts', '--wait', '--url', BASE],
                    [{'id': 'job', 'status': 'queued'},
                     {'jobs': [{'id': 'job', 'status': status}]}], clock=[0, 1])
                self.assertEqual(code, expected)
                self.assertEqual(json.loads(out)['status'], status)
                self.assertEqual(json.loads(requests[0].data)['backend'], 'vts')


if __name__ == '__main__':
    unittest.main()
