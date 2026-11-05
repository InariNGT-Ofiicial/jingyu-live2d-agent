"""Run the existing local CosyVoice preset in its own environment."""
import hashlib,json,sys,time
from pathlib import Path
from studio_voice import load_preset, voice_environment
import os

def run(job_path):
    job=json.loads(Path(job_path).read_text(encoding='utf-8'))
    preset_path=Path(job['preset'])
    p=load_preset(preset_path)
    os.environ.update(voice_environment(p))
    ref=preset_path.parent/p['reference']['file']
    digest=hashlib.sha256(ref.read_bytes()).hexdigest()
    if digest!=p['reference']['sha256']:raise ValueError('参考音频指纹与预设不一致')
    project=Path(p['engine']['project']);src=project/'CosyVoice_源码'
    for path in [project,src,src/'third_party/Matcha-TTS']:sys.path.insert(0,str(path))
    import wetext_local_patch
    wetext_local_patch.apply()
    import torch,numpy as np,soundfile as sf,random
    torch.set_num_threads(p['params']['torch_threads'])
    torch.set_num_interop_threads(p['params']['interop_threads'])
    torch.manual_seed(p['params']['seed'])
    random.seed(p['params']['seed']);np.random.seed(p['params']['seed'])
    from cosyvoice.cli.cosyvoice import AutoModel
    start=time.monotonic()
    model=AutoModel(model_dir=p['engine']['model_dir'])
    loaded=time.monotonic()
    chunks=[x['tts_speech'].detach().cpu().numpy().reshape(-1) for x in model.inference_instruct2(
        job['text'],job['instruction']+p['params']['prompt_suffix'],str(ref),stream=False,speed=p['params']['speed'])]
    audio=np.concatenate(chunks)
    if not len(audio) or not np.isfinite(audio).all():raise ValueError('合成音频为空或包含无效值')
    sf.write(job['output'],audio,model.sample_rate,subtype='PCM_16')
    result={'duration':len(audio)/model.sample_rate,'sampleRate':model.sample_rate,
        'loadSeconds':loaded-start,'synthesisSeconds':time.monotonic()-loaded,
        'referenceSha256':digest,'audioSha256':hashlib.sha256(Path(job['output']).read_bytes()).hexdigest(),
        'peak':float(np.max(np.abs(audio))),'rms':float(np.sqrt(np.mean(audio**2))),
        'presetId':p['id'],'speed':p['params']['speed'],'seed':p['params']['seed']}
    Path(job['result']).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':run(sys.argv[1])
