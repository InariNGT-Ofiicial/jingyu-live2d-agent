"""Native capture contract tests; no VTS window or GPU required."""
import tempfile,time,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from media_exports import ExportManager
from vts_capture import choose_sender,fit_rgba,Recorder

def temporary_directory():
    base=Path(__file__).resolve().parent/'.local/tests';base.mkdir(parents=True,exist_ok=True)
    return tempfile.TemporaryDirectory(dir=base)

class SenderTests(unittest.TestCase):
    def test_never_select_unrelated_or_ambiguous_sender(self):
        for names in [[],['OBS'],['VTubeStudioSpout','VTubeStudioSpout2']]:
            with self.assertRaises(ValueError):choose_sender(names)
        self.assertEqual(choose_sender(['OBS','VTubeStudioSpout']),'VTubeStudioSpout')
        self.assertEqual(choose_sender(['VTubeStudioSpout','VTubeStudioSpout2'],'VTubeStudioSpout2'),'VTubeStudioSpout2')
        with self.assertRaises(ValueError):choose_sender(['VTubeStudioSpout'],'absent')

class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp=temporary_directory();self.addCleanup(self.temp.cleanup)
        self.events=[];self.manager=ExportManager(lambda k,v:self.events.append((k,v)))
        self.manager.scratch=Path(self.temp.name)/'frames';self.manager.output=Path(self.temp.name)/'exports'
    def start(self,**options):
        with patch('media_exports.executable',return_value='ffmpeg'),patch('media_exports.subprocess.run',return_value=SimpleNamespace(stdout=' V..... gif encoder\n V..... libx264 encoder')),patch('media_exports.threading.Thread.start'):
            return self.manager.start({'duration':2},{'renderer':'vts',**options},None)
    def test_native_job_does_not_dispatch_web_frames(self):
        j=self.start();self.assertEqual(j['renderer'],'vts-spout2');self.assertTrue(self.manager.native_busy());self.assertEqual(self.events,[])
        private=self.manager.jobs[j['id']]
        with self.assertRaisesRegex(ValueError,'原生导出'):
            self.manager.frame({'id':j['id'],'token':private['token'],'clientId':None})
        with self.assertRaisesRegex(ValueError,'已有导出'):self.start()
    def test_cancel_keeps_exclusive_ownership_until_worker_recovers(self):
        j=self.start();process=Mock();self.manager.procs[j['id']]=process
        self.assertEqual(self.manager.cancel(j['id'])['status'],'cancelling')
        self.assertTrue((self.manager.scratch/j['id']/'cancel').exists())
        self.assertTrue(self.manager.native_busy());process.terminate.assert_not_called()
        with self.assertRaisesRegex(ValueError,'已有导出'):self.start()
    def test_invalid_renderer_and_transparent_mp4_rejected(self):
        with self.assertRaises(ValueError):self.start(renderer='screen')
        with self.assertRaisesRegex(ValueError,'不支持透明'):self.start(format='mp4',transparent=True)
    def test_server_uses_one_reentrant_lock_for_jobs_and_events(self):
        import server
        self.assertIs(server.EXPORTS.lock,server.LOCK)

try:
    from PIL import Image
except ImportError:Image=None

@unittest.skipUnless(Image,'Install requirements-capture.txt for RGBA recorder tests')
class RecordingTests(unittest.TestCase):
    def test_fit_preserves_aspect_ratio_and_half_alpha(self):
        out=fit_rgba(Image.new('RGBA',(400,200),(120,80,40,128)),100,100)
        self.assertEqual(out.size,(100,100));self.assertEqual(out.getbbox(),(0,25,100,75))
        self.assertEqual(out.getpixel((50,50))[3],128)
        self.assertEqual(out.getpixel((0,0))[3],0)

    def record(self,mode='moving'):
        class FakeReceiver:
            name='VTubeStudioSpout';gpu='test';index=0
            def read(self,timeout=2,expected=None):
                self.index+=1
                if mode=='resize' and expected:raise RuntimeError('VTS 输出尺寸改变')
                color=(self.index*17%255 if mode!='frozen' else 80,100,120,255)
                im=Image.new('RGBA',(4,4),(0,0,0,0));im.putpixel((2,2),color)
                if mode=='opaque':im=Image.new('RGBA',(4,4),color)
                return im.tobytes(),(4,4),0  # VTS may not publish a sender counter.
            def close(self):pass
        with temporary_directory() as d,patch('vts_capture.Receiver',side_effect=lambda _:FakeReceiver()):
            folder=Path(d);r=Recorder({'format':'gif','width':16,'height':16,'fps':100,'frameCount':5},folder,folder/'cancel')
            try:
                r.wait(r.ready,2)
                try:r.prepare();r.start(time.monotonic());r.wait(r.done,2)
                except RuntimeError:pass
                return r.error,r.result,len(list(folder.glob('*.png'))),(folder/'cancel').exists()
            finally:r.close()
    def test_real_rgba_frames_written_without_sender_counter(self):
        error,result,count,cancelled=self.record()
        self.assertIsNone(error);self.assertEqual(count,5);self.assertEqual(result['uniqueFrames'],5)
        self.assertFalse(result['senderFrameCounterAvailable']);self.assertFalse(cancelled)
    def test_opaque_gif_is_an_error(self):
        error,_,count,cancelled=self.record('opaque')
        self.assertIn('未输出透明',error);self.assertEqual(count,0);self.assertTrue(cancelled)
    def test_frozen_stream_is_not_success(self):
        error,result,_,cancelled=self.record('frozen')
        self.assertIn('完全相同',error);self.assertEqual(result,{});self.assertTrue(cancelled)
    def test_resize_aborts_and_requests_vts_recovery(self):
        error,_,count,cancelled=self.record('resize')
        self.assertIn('尺寸改变',error);self.assertEqual(count,0);self.assertTrue(cancelled)

if __name__=='__main__':unittest.main()
