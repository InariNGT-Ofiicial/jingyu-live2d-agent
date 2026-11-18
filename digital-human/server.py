"""Private H3/A3 conversation prototype; serves one operator at a time on loopback."""
import asyncio,base64,json,os,re,sys,threading,subprocess
from collections import defaultdict
from pathlib import Path
import aiohttp
from aiohttp import web
import numpy as np
import torch
from local_choice import choose
from transformers import AutoModelForCausalLM,AutoModelForMultimodalLM,AutoTokenizer,AutoProcessor
from router import CATALOG,ROOT,select,ALIASES,normal
from decision import control,behavior
from phone_context import complete_reply,needs_brief,needs_detail,phone_messages,speech_parts
from mobile_access import MobileAccess

from settings import DECISION, ASR, LOCAL, NAME, PORT, WORKER
os.environ.setdefault('CALL_FAST_A3','1')
from viewer_memory import recall_name,recall
gate=threading.Lock()
def phone_mp3(pcm):
    result=subprocess.run(['ffmpeg','-v','error','-f','s16le','-ar','24000','-ac','1','-i','pipe:0',
                           '-c:a','libmp3lame','-b:a','64k','-f','mp3','pipe:1'],
                          input=pcm,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=2,check=True)
    return result.stdout
jev=os.environ.get('DIALOGUE_USE_JEV')=='1' and bool(os.environ.get('TYPESAFE_API_KEY'))
class Models:
    def intent(self,text):
        with gate:return choose(self.chat,self.tok,text)[0]
    def __init__(self):
        p=DECISION
        self.tok=AutoTokenizer.from_pretrained(p)
        self.chat=AutoModelForCausalLM.from_pretrained(p,dtype=torch.bfloat16).cuda().eval()
        path=ASR
        self.proc=AutoProcessor.from_pretrained(path)
        self.asr=AutoModelForMultimodalLM.from_pretrained(path,dtype=torch.bfloat16).cuda().eval()
    @torch.inference_mode()
    def transcribe(self,pcm):
        wave=np.frombuffer(pcm,'<i2').astype('float32')/32768
        if not len(wave) or np.sqrt(np.mean(wave**2))<.002:return ''
        with gate:
            inp=self.proc.apply_transcription_request(audio=wave,language='Chinese').to(self.asr.device,self.asr.dtype)
            out=self.asr.generate(**inp,max_new_tokens=100,do_sample=False)
            text=self.proc.decode(out[:,inp['input_ids'].shape[1]:],return_format='transcription_only')[0].strip()
            return re.sub(r'(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])','',text)
    @torch.inference_mode()
    def answer(self,text,history,phone=False):
        instruction='你是DeepseekChan，鲸语直播间的数字人。直接回应当前观众，参考这个观众刚才的对话，用自然中文说一到两句，尽量在35字内说完。'
        turns=[dict(role='system',content=instruction.replace('DeepseekChan',NAME))]
        for h in history[-4:]:turns.extend([dict(role='user',content=h['text']),dict(role='assistant',content=h['reply'])])
        turns.append(dict(role='user',content=text))
        if phone:turns=phone_messages(text,history)
        with gate:
            prompt=self.tok.apply_chat_template(turns,tokenize=False,add_generation_prompt=True)
            x=self.tok(prompt,return_tensors='pt').to(self.chat.device)
            brief=phone and needs_brief(text)
            limit=(256 if needs_detail(text) else 160) if phone and not brief else 60
            opts={'stop_strings':['。','！','？'],'tokenizer':self.tok} if brief else {}
            y=self.chat.generate(**x,max_new_tokens=limit,do_sample=False,pad_token_id=self.tok.eos_token_id,**opts)
            reply=self.tok.decode(y[0,x.input_ids.shape[1]:],skip_special_tokens=True).strip()
            return complete_reply(reply,y.shape[1]-x.input_ids.shape[1]==limit) if phone else reply[:160]

async def socket(req):
    origin=req.headers.get('Origin')
    if not MobileAccess.public(req) and origin and origin!='http://'+req.host:return web.Response(status=403)
    ws=web.WebSocketResponse(max_msg_size=2*1024**2,heartbeat=20)
    await ws.prepare(req)
    seat=req.app['operator'];previous=seat[0];seat[0]=ws
    if previous is not None and not previous.closed:
        asyncio.create_task(previous.close(code=1001,message=b'new operator page'))
    revision=0;tasks=set();history=defaultdict(list);last={};awaiting={}
    draft=None;asr_work=None
    http=req.app['http'];models=req.app['models']
    async def fast_answer(text,prior):
        async with http.post(WORKER+'/answer',json={'text':text,'history':list(prior)},timeout=aiohttp.ClientTimeout(total=8)) as r:
            r.raise_for_status();return (await r.json())['reply'].strip()
    async def fast_voice(reply):
        async with http.post(WORKER+'/speak',json={'text':reply},timeout=aiohttp.ClientTimeout(total=12)) as r:
            r.raise_for_status();pcm=await r.read()
        if not pcm or len(pcm)%2:raise ValueError('A3 返回无效音频')
        return pcm
    async def preview(asr,who):
        # Render in the final silence. The actual turn must match this exact audio
        # and viewer before any text, history entry, or sound can be published.
        await asyncio.sleep(.18)
        text=await asyncio.shield(asr)
        prior=list(history[who])
        if not text or normal(text) in ALIASES or control(text,prior) or recall.search(text):return None
        reply=await fast_answer(text,prior)
        return (reply,await fast_voice(speech_parts(reply)[0])) if reply else None
    async def turn(d,seq,prepared=None,prediction=None):
        async def send(kind,**props):
            if revision==seq and not ws.closed:await ws.send_json(dict(type=kind,id=seq,**props))
        try:
            who=str(d.get('viewer','观众'))[:30];prior=history[who]
            if 'audio' in d:
                pcm=base64.b64decode(d['audio'],validate=True)
                if len(pcm)>16000*2*30 or len(pcm)%2:raise ValueError('语音限 30 秒单声道 PCM')
                text=await prepared if prepared is not None else await asyncio.to_thread(models.transcribe,pcm)
            else:text=str(d.get('text','')).strip()
            if revision!=seq:return
            if not text or len(text)>500:raise ValueError('没有识别到有效短句')
            await send('input',text=text,viewer=who)
            awaiting[seq]=(who,text,'','answer')
            phone=d.get('phone') is True
            intent=control(text,prior)
            if intent:selector='exact'
            else:intent,selector=await asyncio.to_thread(select,text,prior,jev)
            if selector=='local_fallback' and len(text)<=20 and not recall.search(text) and not (phone and (prior or needs_detail(text))):
                intent=await asyncio.to_thread(models.intent,text)
                selector='local_choice' if intent else 'local_abstain'
            if revision!=seq:return
            if intent:
                preset=CATALOG[intent];index=(last.get(intent,-1)+1)%len(preset['lines']);last[intent]=index
                reply=preset['lines'][index];awaiting[seq]=(who,text,reply,'preset')
                await send('cached',key=f'{intent}-{index}',reply=reply,route='预设',selector=selector,action=preset['action'],behavior=behavior(intent))
                return
            reply=recall_name(prior,who,text)
            if not reply and recall.search(text):
                reply='我还没记下你的名字，怎么称呼你呀？'
            route='记忆＋A3' if reply else '模型＋A3'
            history_kind='memory' if reply else 'answer'
            await send('thinking',route=route,selector=selector)
            early_pcm=None
            if not reply and phone and os.environ.get('CALL_FAST_A3')=='1':
                try:
                    early=await prediction if prediction else None
                    if early:reply,early_pcm=early
                    else:reply=await fast_answer(text,prior)
                except (aiohttp.ClientError,TimeoutError,ValueError):
                    pass
            if not reply:
                reply=await asyncio.to_thread(models.answer,text,list(prior),phone)
            if revision!=seq:return
            if not reply:raise ValueError('没有生成回复')
            if phone and os.environ.get('CALL_FAST_A3')=='1':
                parts=speech_parts(reply)
                sent_parts=0
                try:
                    if d.get('segmentedAudio') is True:
                        await send('reply',reply=reply,route=route)
                        for index,part in enumerate(parts):
                            if revision!=seq:return
                            pcm=early_pcm if index==0 and early_pcm else await fast_voice(part)
                            if revision!=seq:return
                            encoded=None
                            if d.get('compactOutput') is True:
                                try:encoded=await asyncio.to_thread(phone_mp3,pcm)
                                except (OSError,subprocess.SubprocessError):pass
                            if revision!=seq:return
                            await send('voice_part',data=base64.b64encode(encoded or pcm).decode(),
                                       codec='mp3' if encoded else 'pcm',part=index,chars=sum(map(len,parts[:index+1])),engine='call-a3')
                            sent_parts+=1
                            awaiting[seq]=(who,text,reply[:sum(map(len,parts[:index+1]))],history_kind)
                        await send('end');return
                    chunks=[]
                    for index,part in enumerate(parts):
                        if revision!=seq:return
                        chunks.append(early_pcm if index==0 and early_pcm else await fast_voice(part))
                    pcm=b''.join(chunks)
                except (aiohttp.ClientError,TimeoutError,ValueError):
                    if sent_parts:raise
                    pass  # Studio streaming remains available if the call-specific worker is offline.
                else:
                    if revision!=seq:return
                    awaiting[seq]=(who,text,reply,history_kind)
                    await send('reply',reply=reply,route=route)
                    if d.get('compactOutput') is True:
                        try:encoded=await asyncio.to_thread(phone_mp3,pcm)
                        except (OSError,subprocess.SubprocessError):encoded=None
                        if encoded:
                            await send('voice_file',data=base64.b64encode(encoded).decode(),engine='call-a3')
                            return
                    await send('pcm',data=base64.b64encode(pcm).decode(),engine='call-a3')
                    await send('end');return
            raise RuntimeError('语音进程未返回有效录音，请检查 synthesis.py 的终端。')
        except Exception as exc:await send('error',message=str(exc))
    try:
        async for event in ws:
            if event.type!=aiohttp.WSMsgType.TEXT:break
            d=json.loads(event.data);seq=int(d.get('id',0))
            if d['type']=='draft' and seq==revision+1:
                if draft and draft[4]:draft[4].cancel()
                raw=d.get('audio','')
                if len(raw)>1280000:continue
                pcm=base64.b64decode(raw,validate=True)
                if len(pcm)>960000 or len(pcm)%2:continue
                task=None
                if not asr_work or asr_work.done():
                    task=asr_work=asyncio.create_task(asyncio.to_thread(models.transcribe,pcm))
                    task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
                who=str(d.get('viewer','观众'))[:30]
                prediction=None
                if task and d.get('phone') and not jev and os.environ.get('CALL_FAST_A3')=='1':
                    prediction=asyncio.create_task(preview(task,who))
                    prediction.add_done_callback(lambda t:t.exception() if not t.cancelled() else None)
                draft=(seq,raw,task,d.get('draftKey'),prediction,who)
            elif d['type']=='continued' and draft and seq==draft[0] and d.get('draftKey')==draft[3]:
                if draft[4]:draft[4].cancel()
                draft=None
            elif d['type']=='played' and seq==revision and seq in awaiting:
                who,t,r,kind=awaiting.pop(seq);history[who].append(dict(author=who,text=t,reply=r,kind=kind));history[who]=history[who][-48:]
            elif d['type'] in ('turn','stop') and seq>revision:
                if d['type']=='turn' and 'draftKey' in d and draft and draft[0]==seq and draft[3]==d['draftKey']:
                    d['audio']=draft[1]
                prepared=draft[2] if draft and draft[:2]==(seq,d.get('audio')) else None
                prediction=draft[4] if prepared and draft[5]==str(d.get('viewer','观众'))[:30] else None
                if draft and draft[4] and not prediction:draft[4].cancel()
                draft=None
                old=revision;revision=seq
                if old in awaiting:
                    who,t,r,kind=awaiting.pop(old)
                    if isinstance(d.get('spokenChars'),int):r=r[:max(0,d['spokenChars'])]
                    history[who].append(dict(author=who,text=t,reply=r if d.get('heardPrevious') is True else '',kind=kind,interrupted=True))
                    history[who]=history[who][-48:]
                if d['type']=='turn':
                    task=asyncio.create_task(turn(d,seq,prepared,prediction));tasks.add(task);task.add_done_callback(tasks.discard)
    finally:
        if draft and draft[4]:draft[4].cancel()
        if seat[0] is ws:seat[0]=None
        revision+=1
        if tasks:await asyncio.gather(*list(tasks),return_exceptions=True)
    return ws
async def main():
    torch.set_num_threads(3);models=Models()
    await asyncio.to_thread(models.answer,'你好',[])
    if os.environ.get('CALL_FAST_A3')=='1':await asyncio.to_thread(models.answer,'现在适合聊天吗？',[],True)
    manifest=json.loads((LOCAL/'audio/manifest.json').read_text())
    async def home(req):return web.Response(text=(ROOT/'stage.html').read_text(encoding='utf8').replace('DeepseekChan',NAME),content_type='text/html')
    async def config(req):return web.json_response(dict(audio=[r['id'] for r in manifest],audioHashes={r['id']:r['sha256'][:16] for r in manifest},jev=jev))
    mobile=MobileAccess(ROOT,[r['id'] for r in manifest])
    app=web.Application(middlewares=[mobile.guard]);app['http']=aiohttp.ClientSession();app['models']=models;app['operator']=[None]
    app.router.add_get('/',home);app.router.add_get('/config',config);app.router.add_get('/ws',socket)
    app.router.add_static('/audio/',LOCAL/'audio');app.router.add_static('/motions/phone/',ROOT/'web');app.router.add_static('/motions/',LOCAL/'assets')
    app.router.add_get('/client.js',lambda _:web.FileResponse(ROOT/'client.js'))
    runner=web.AppRunner(app);await runner.setup();await web.TCPSite(runner,'127.0.0.1',PORT).start()
    if mobile.origin:await web.TCPSite(runner,'127.0.0.1',6006).start()
    print('READY',flush=True);await asyncio.Event().wait()
if __name__=='__main__':asyncio.run(main())
