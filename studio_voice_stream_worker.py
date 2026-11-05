"""Resident CosyVoice process. stdin commands / stdout JSON events; diagnostics on stderr."""
import base64
import hashlib
import json
import os
from pathlib import Path
import queue
import random
import sys
import threading
import time
from studio_voice import load_preset, voice_environment


def run(preset_file, cache_dir):
    protocol = sys.stdout
    sys.stdout = sys.stderr
    def emit(kind, **data):
        protocol.write(json.dumps({'type': kind, **data}, ensure_ascii=False) + '\n')
        protocol.flush()
    emit('engine', status='loading', phase='dependencies')
    import faulthandler
    faulthandler.dump_traceback_later(60, repeat=True)
    commands = queue.Queue()
    cancelled = set()
    shutdown = threading.Event()
    def read_commands():
        try:
            for line in sys.stdin:
                command = json.loads(line)
                if command['type'] == 'cancel':
                    cancelled.add(command['id'])
                commands.put(command)
        finally:
            shutdown.set()
            commands.put({'type': 'shutdown'})
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.update(NUMBA_CACHE_DIR=str(cache), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    preset_path = Path(preset_file)
    preset = load_preset(preset_path)
    os.environ.update(voice_environment(preset))
    ref = preset_path.parent / preset['reference']['file']
    if hashlib.sha256(ref.read_bytes()).hexdigest() != preset['reference']['sha256']:
        raise ValueError('参考音频指纹与预设不一致')
    project = Path(preset['engine']['project'])
    for path in [project, project/'CosyVoice_源码', project/'CosyVoice_源码/third_party/Matcha-TTS']:
        sys.path.insert(0, str(path))
    import wetext_local_patch
    wetext_local_patch.apply()
    import numpy as np
    import soundfile as sf
    import torch
    torch.set_num_threads(preset['params']['torch_threads'])
    torch.set_num_interop_threads(preset['params']['interop_threads'])
    from cosyvoice.cli.cosyvoice import AutoModel
    started = time.monotonic()
    model = AutoModel(model_dir=preset['engine']['model_dir'], fp16=torch.cuda.is_available())
    # Cache the reference features once; refresh instruction tokens separately per job.
    model.add_zero_shot_spk('', str(ref), 'jingyu-stream')
    faulthandler.cancel_dump_traceback_later()
    # Load native numerical libraries before starting a blocked Windows stdin reader.
    threading.Thread(target=read_commands, daemon=True).start()
    emit('engine', status='ready', sampleRate=model.sample_rate,
         loadSeconds=time.monotonic()-started, device=str(model.model.device))
    job = None
    wav = None
    samples = 0
    while True:
        command = commands.get()
        kind, jid = command['type'], command.get('id')
        if kind == 'shutdown' or shutdown.is_set():
            if wav:
                wav.close()
            return
        if kind == 'cancel':
            if job and job['id'] == jid:
                wav.close()
                wav = None
                job = None
            cancelled.discard(jid)
            emit('released', id=jid)
            continue
        if jid in cancelled:
            continue
        try:
            if kind == 'begin':
                if wav:
                    raise ValueError('上个语音任务尚未结束')
                job = command
                samples = 0
                random.seed(preset['params']['seed'])
                np.random.seed(preset['params']['seed'])
                torch.manual_seed(preset['params']['seed'])
                instruction = command['instruction'] + preset['params']['prompt_suffix']
                tokens, length = model.frontend._extract_text_token(instruction)
                model.frontend.spk2info['jingyu-stream'].update(prompt_text=tokens, prompt_text_len=length)
                wav = sf.SoundFile(command['output'], mode='w', samplerate=model.sample_rate,
                                   channels=1, subtype='PCM_16')
                emit('start', id=jid, sampleRate=model.sample_rate, format='s16le', channels=1)
            elif job and job['id'] == jid and kind == 'segment':
                model.model.token_hop_len = 25
                emit('segment', id=jid, text=command['text'], offsetSamples=samples)
                for result in model.inference_instruct2(command['text'], instruction, str(ref),
                        zero_shot_spk_id='jingyu-stream', stream=True, speed=1.0):
                    if shutdown.is_set():
                        wav.close()
                        return
                    # Drain a cancelled segment so upstream releases its caches/LLM thread.
                    if jid in cancelled:
                        continue
                    audio = result['tts_speech'].detach().cpu().numpy().reshape(-1)
                    if not len(audio) or not np.isfinite(audio).all():
                        raise ValueError('合成返回了无效音频')
                    pcm = (np.clip(audio, -1, 1) * 32767).astype('<i2')
                    wav.write(pcm)
                    emit('pcm', id=jid, samples=len(pcm), offsetSamples=samples,
                         data=base64.b64encode(pcm.tobytes()).decode('ascii'))
                    samples += len(pcm)
            elif job and job['id'] == jid and kind == 'end':
                wav.close()
                wav = None
                job = None
                emit('done', id=jid, duration=samples/model.sample_rate,
                     sampleRate=model.sample_rate, samples=samples,
                     referenceSha256=preset['reference']['sha256'], speed=1.0)
        except Exception:
            if wav:
                wav.close()
            import traceback
            traceback.print_exc()
            # A failed upstream generator may leave GPU state or threads alive. Restart explicitly.
            emit('error', id=jid, error='本地流式合成失败，请查看 resident.log；下次请求会重新加载')
            return


if __name__ == '__main__':
    run(sys.argv[1], sys.argv[2])
