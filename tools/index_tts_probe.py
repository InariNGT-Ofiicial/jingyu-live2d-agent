"""IndexTTS 2.5: inspect local prerequisites, or explicitly run a DS-voice comparison."""
import argparse,json,sys,time,hashlib
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',required=True);p.add_argument('--model',required=True)
    p.add_argument('--preset',required=True);p.add_argument('--output',default='index-comparison')
    p.add_argument('--text',default='晚上好，我是 DS 娘。欢迎来到雨夜书房，今天想和我聊些什么？')
    p.add_argument('--run',action='store_true');a=p.parse_args()
    repo=Path(a.repo).resolve();model=Path(a.model).resolve();preset=Path(a.preset).resolve()
    required=['config.yaml','gpt.pth','s2mel.pth','codec.pth','multilingual_zh_ja_yue_char_del.tiktoken','wav2vec2bert_stats.pt','feat1.pt','feat2.pt']
    missing=[name for name in required if not (model/name).is_file()]
    info={'python':sys.version.split()[0],'supportedPython':(3,10)<=sys.version_info[:2]<(3,12),
        'sourcePresent':(repo/'indextts/infer_v2_5.py').is_file(),'missingMainFiles':missing,
        'model':str(model),'mode':'inference' if a.run else 'probe'}
    print(json.dumps(info,ensure_ascii=False,indent=2))
    if not a.run:return
    if missing or not info['sourcePresent'] or not info['supportedPython']:p.error('请先在独立 Python 3.10/3.11 环境准备官方依赖和权重')
    cfg=json.loads(preset.read_text(encoding='utf-8-sig'));ref=preset.parent/cfg['reference']['file']
    if hashlib.sha256(ref.read_bytes()).hexdigest()!=cfg['reference']['sha256']:p.error('参考音频指纹不匹配')
    sys.path.insert(0,str(repo))
    from indextts.infer_v2_5 import IndexTTS2
    import torch,soundfile as sf
    out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    start=time.monotonic()
    tts=IndexTTS2(cfg_path=str(model/'config.yaml'),model_dir=str(model),use_bf16=True,
        use_cuda_kernel=False,use_deepspeed=False,use_accel=False,use_torch_compile=False,use_qwen_emo=False)
    rows=[];load=time.monotonic()-start
    for name,emotion,factor in [('neutral',[0,0,0,0,0,0,0,0],1),('happy',[.5,0,0,0,0,0,0,0],1),('slow',[0,0,0,0,0,0,0,0],1.15)]:
        torch.manual_seed(cfg['params']['seed']);torch.cuda.reset_peak_memory_stats()
        target=out/(name+'.wav');start=time.monotonic()
        tts.infer(spk_audio_prompt=str(ref),text=a.text,lang='ZH',output_path=str(target),
            emo_vector=emotion,use_random=False,duration_factor=factor)
        elapsed=time.monotonic()-start;audio=sf.info(target)
        rows.append({'id':name,'seconds':audio.duration,'sampleRate':audio.samplerate,
            'inferenceSeconds':elapsed,'rtf':elapsed/audio.duration,'peakVramBytes':torch.cuda.max_memory_allocated(),
            'emotion':emotion,'durationFactor':factor,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
        (out/'results.json').write_text(json.dumps({'text':a.text,'referenceSha256':cfg['reference']['sha256'],
            'loadSeconds':load,'takes':rows},ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
