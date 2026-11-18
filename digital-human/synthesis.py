"""Private, serial A3 accelerator. The studio voice preset and checkpoint remain the source."""
import asyncio,base64,hashlib,json,os,random,sys,time
from pathlib import Path
import numpy as np
from aiohttp import web

from settings import DECISION, COSY_MODEL, COSY_SOURCE, REFERENCE, VOICE_PORT, LOCAL
sys.path[:0]=[str(COSY_SOURCE),str(COSY_SOURCE/'third_party/Matcha-TTS')]
import torch
from cosyvoice.cli.cosyvoice import AutoModel
from speech_decode import SpeechDecoder
from phone_chat import PhoneChat

torch.set_num_threads(2)
torch.set_num_interop_threads(1)
ref=REFERENCE
if not ref.is_file():raise SystemExit('请先配置角色参考音频 JINGYU_VOICE_REFERENCE。')
rules=Path(os.environ.get('JINGYU_WETEXT', LOCAL/'models/wetext'))
if rules.is_dir():
    from unittest.mock import patch
    from wetext import wetext
    for language in ('zh','en'):
        for filename in ('tagger.fst','verbalizer.fst'):
            if not (rules/language/'tn'/filename).is_file():raise SystemExit(f'缺少 WeText 规则 {language}/tn/{filename}')
    # The installed WeText release resolves a snapshot during frontend construction.
    with patch.object(wetext,'snapshot_download',return_value=str(rules.resolve())):
        model=AutoModel(model_dir=str(COSY_MODEL),fp16=True)
else:
    model=AutoModel(model_dir=str(COSY_MODEL),fp16=True)
model.add_zero_shot_spk('',str(ref),'call-a3')
instruction=os.environ.get('JINGYU_VOICE_STYLE','用自然、平稳、像和朋友聊天的语气说。')+'<|endofprompt|>'
tokens,length=model.frontend._extract_text_token(instruction)
model.frontend.spk2info['call-a3'].update(prompt_text=tokens,prompt_text_len=length)
decoder=SpeechDecoder(model.model.llm)
model.model.llm.inference_wrapper=decoder.decode

def render(text):
    seed=20261016
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    # Return the complete speech waveform so playback cannot run out at a chunk boundary.
    audio=[]
    for r in model.inference_instruct2(text,instruction,str(ref),zero_shot_spk_id='call-a3',stream=False,speed=1.0):
        audio.append(r['tts_speech'].detach().float().cpu().numpy().ravel())
    x=np.concatenate(audio)
    assert np.isfinite(x).all() and len(x)>0
    pcm=(np.clip(x,-1,1)*32767).astype('<i2')
    # Remove only verified leading silence, keeping 50 ms before the first quiet consonant.
    blocks=pcm[:len(pcm)//120*120].astype(float).reshape(-1,120)
    above=np.mean(blocks*blocks,axis=1)>75**2
    onset=np.flatnonzero(above[:-1]&above[1:])
    if len(onset):pcm=pcm[max(0,int(onset[0])*120-1200):]
    return pcm.tobytes()

async def main():
    # Warm CUDA capture, Flow and vocoder ahead of the first phone call.
    for line in ['你好呀，欢迎来聊天。','今天天气刚好，适合出去散散步。']:
        start=time.monotonic(); b=await asyncio.to_thread(render,line)
        print('warm',round(time.monotonic()-start,3),len(b)/48000,flush=True)
    chat=PhoneChat(DECISION)
    for q in ['你好','现在适合聊点什么？']:
        print('chat warm',await asyncio.to_thread(chat.answer,q,[]),flush=True)
    lock=asyncio.Lock()
    async def respond(req):
        d=await req.json()
        # A cancelled browser turn can still be finishing a short GPU render.
        # Keep the next turn on the warm A3 engine instead of falling back cold.
        async with lock:
            result=await asyncio.to_thread(chat.answer,d['text'],d['history'])
        return web.json_response({'reply':result})
    async def speak(req):
        body=await req.json();text=str(body.get('text','')).strip()
        if not 0<len(text)<=160:raise web.HTTPBadRequest()
        async with lock:
            pcm=await asyncio.to_thread(render,text)
        return web.Response(body=pcm,content_type='application/octet-stream')
    app=web.Application();app.router.add_post('/speak',speak);app.router.add_post('/answer',respond)
    runner=web.AppRunner(app);await runner.setup()
    await web.TCPSite(runner,'127.0.0.1',VOICE_PORT).start()
    print('READY',flush=True);await asyncio.Event().wait()

if __name__=='__main__':asyncio.run(main())
