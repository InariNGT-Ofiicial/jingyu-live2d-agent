"""Local DS voice streaming benchmark; no cloud calls or model-file changes.

Run with the Python interpreter specified by the existing voice preset.
The incremental text producer is simulated, NOT a live LLM.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import random
import sys
import threading
import time


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--preset', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--play', action='store_true', help='Play only the final incremental trial')
    parser.add_argument('--fp16', action='store_true', help='Use upstream half precision inference')
    parser.add_argument('--sentence-only', action='store_true', help='Stream semantic segments through instruct2')
    parser.add_argument('--startup-buffer', type=float, default=0, help='Seconds to wait after first PCM before playback')
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    # Numba otherwise tries writing beside the read-only external dependencies.
    cache = out / 'numba-cache'
    cache.mkdir(exist_ok=True)
    os.environ['NUMBA_CACHE_DIR'] = str(cache.resolve())
    preset_path = Path(args.preset)
    p = json.loads(preset_path.read_text(encoding='utf-8-sig'))
    ref = preset_path.parent / p['reference']['file']
    assert hashlib.sha256(ref.read_bytes()).hexdigest() == p['reference']['sha256']
    project = Path(p['engine']['project'])
    for path in [project, project / 'CosyVoice_源码', project / 'CosyVoice_源码/third_party/Matcha-TTS']:
        sys.path.insert(0, str(path))
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    print('Loading local dependencies...', flush=True)
    import wetext_local_patch
    wetext_local_patch.apply()
    import numpy as np
    import soundfile as sf
    import torch
    torch.set_num_threads(p['params']['torch_threads'])
    torch.set_num_interop_threads(p['params']['interop_threads'])
    from cosyvoice.cli.cosyvoice import AutoModel
    print('Loading CosyVoice2 model...', flush=True)
    started = time.perf_counter()
    model = AutoModel(model_dir=p['engine']['model_dir'], fp16=args.fp16)
    load_seconds = time.perf_counter() - started
    print(json.dumps({'modelLoadSeconds': load_seconds}), flush=True)
    instruction = p['params']['instruction'] + p['params']['prompt_suffix']
    started = time.perf_counter()
    # Cache conditioning only in memory. Do not call save_spkinfo().
    model.add_zero_shot_spk(instruction, str(ref), 'stream-probe')
    report = {'modelLoadSeconds': load_seconds, 'conditioningSeconds': time.perf_counter() - started,
              'device': str(model.model.device), 'sampleRate': model.sample_rate, 'fp16': args.fp16,
              'referenceSha256': p['reference']['sha256'], 'trials': [],
              'note': 'Incremental text is a timed local simulation, not an LLM response.'}
    parts = ['你好，我是晓伊。', '这次不用等整段话生成完，', '我就可以先开口。',
             '后面的文字还在陆续送来，', '声音也会一边合成，一边播放。', '这样聊天就更自然了。']

    def trial(name, streaming, incremental=False, speed=1.0, play=False, segmented=False):
        random.seed(p['params']['seed'])
        np.random.seed(p['params']['seed'])
        torch.manual_seed(p['params']['seed'])
        # Upstream mutates this across calls; reset for comparable first chunks.
        model.model.token_hop_len = 25
        begin = time.perf_counter()
        events, chunks = [], []
        source = queue.Queue()
        def produce():
            for i, part in enumerate(parts):
                if i:
                    time.sleep(0.8)
                events.append({'kind': 'text', 'at': time.perf_counter() - begin, 'text': part})
                source.put(part)
            source.put(None)
        def text_generator():
            while True:
                part = source.get()
                if part is None:
                    return
                yield part
        if incremental:
            producer = threading.Thread(target=produce, daemon=True)
            producer.start()
        player = None
        playback = {'enabled': play, 'firstCallbackSeconds': None, 'underflowCallbacks': 0}
        pcm_queue = queue.Queue()
        remaining = np.empty(0, dtype=np.float32)
        done = threading.Event()
        ended = threading.Event()
        playback_ready_at = 0.0
        def callback(output, frames, timing, status):
            nonlocal remaining
            output.fill(0)
            if playback['firstCallbackSeconds'] is None:
                playback['firstCallbackSeconds'] = time.perf_counter() - begin
            if status.output_underflow:
                playback['underflowCallbacks'] += 1
            if time.perf_counter() < playback_ready_at:
                return
            offset = 0
            while offset < frames:
                if not len(remaining):
                    try:
                        remaining = pcm_queue.get_nowait()
                    except queue.Empty:
                        if done.is_set():
                            import sounddevice as sd
                            raise sd.CallbackStop
                        playback['emptyQueueFrames'] = playback.get('emptyQueueFrames', 0) + frames - offset
                        break
                count = min(frames - offset, len(remaining))
                if 'firstContentSeconds' not in playback:
                    playback['firstContentSeconds'] = time.perf_counter() - begin
                output[offset:offset + count, 0] = remaining[:count]
                remaining = remaining[count:]
                offset += count
        def segments():
            text = ''
            for part in text_generator():
                text += part
                if len(text) >= 24 and text.endswith(('。', '！', '？')):
                    yield text
                    text = ''
            if text:
                yield text
        def synthesize():
            inputs = segments() if segmented else [text_generator() if incremental else ''.join(parts)]
            for text in inputs:
                model.model.token_hop_len = 25
                if segmented:
                    events.append({'kind': 'segment', 'at': time.perf_counter() - begin, 'text': text})
                yield from model.inference_instruct2(text, instruction, str(ref), zero_shot_spk_id='stream-probe',
                                                     stream=streaming, speed=speed)
        try:
            for result in synthesize():
                audio = result['tts_speech'].detach().cpu().numpy().reshape(-1).astype(np.float32)
                if not len(audio) or not np.isfinite(audio).all():
                    raise ValueError('Empty or non-finite audio')
                event = {'kind': 'audio', 'at': time.perf_counter() - begin,
                         'seconds': len(audio) / model.sample_rate, 'samples': len(audio)}
                events.append(event)
                chunks.append(audio)
                print(json.dumps({'trial': name, **event}), flush=True)
                if play:
                    pcm_queue.put(audio)
                    if player is None:
                        import sounddevice as sd
                        playback_ready_at = begin + event['at'] + args.startup_buffer
                        player = sd.OutputStream(samplerate=model.sample_rate, channels=1, dtype='float32',
                                                 callback=callback, finished_callback=ended.set, blocksize=480)
                        player.start()
            synthesis_seconds = time.perf_counter() - begin
            done.set()
            if player is not None and not ended.wait(sum(len(c) for c in chunks) / model.sample_rate + 5):
                raise TimeoutError('Playback did not drain')
        finally:
            done.set()
            if player is not None:
                player.stop()
                player.close()
        audio = np.concatenate(chunks)
        sf.write(out / (name + '.wav'), audio, model.sample_rate, subtype='PCM_16')
        packets = [e for e in events if e['kind'] == 'audio']
        duration = len(audio) / model.sample_rate
        first = packets[0]['at']
        delivered = 0.0
        # Extra startup buffer required for uninterrupted playback of this recorded arrival trace.
        buffer_needed = 0.0
        for packet in packets:
            buffer_needed = max(buffer_needed, packet['at'] - first - delivered)
            delivered += packet['seconds']
        result = {'name': name, 'stream': streaming, 'simulatedTextStream': incremental, 'speed': speed,
                  'semanticSegments': segmented, 'startupBufferSeconds': args.startup_buffer,
                  'firstAudioSeconds': first, 'synthesisSeconds': synthesis_seconds, 'audioSeconds': duration,
                  'rtf': synthesis_seconds / duration, 'chunks': len(chunks),
                  'traceExtraBufferSeconds': buffer_needed, 'playback': playback,
                  'peak': float(np.max(np.abs(audio))), 'events': sorted(events, key=lambda e: e['at'])}
        report['trials'].append(result)
        (out / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({k: v for k, v in result.items() if k != 'events'}), flush=True)

    if args.sentence_only:
        trial('sentence-pipeline', True, incremental=True, play=args.play, segmented=True)
        return
    trial('baseline-full', False, speed=p['params']['speed'])
    trial('stream-first', True)
    trial('stream-warm', True)
    trial('bistream-play', True, incremental=True, play=args.play)


if __name__ == '__main__':
    main()
