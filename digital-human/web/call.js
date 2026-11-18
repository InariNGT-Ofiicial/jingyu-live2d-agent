import {micBlocks} from './duplex.js';
const callName=document.querySelector('.identity h1').textContent;
const $=s=>document.querySelector(s), phone=$('#phone');
const paths={
 video:'M3 6h11v12H3z M14 10l6-4v12l-6-4',
 phone:'M5 3l4 1 1 4-2 2a13 13 0 0 0 6 6l2-2 4 1 1 4c0 2-2 3-4 2C10 19 5 14 3 7 2 5 3 3 5 3z',
 end:'M3 16l4-1 1-4a17 17 0 0 1 8 0l1 4 4 1c1-1 1-4-1-6-4-4-12-4-16 0-2 2-2 5-1 6z',
 mic:'M9 5a3 3 0 0 1 6 0v7a3 3 0 0 1-6 0z M5 11a7 7 0 0 0 14 0 M12 18v4 M9 22h6',
 volume:'M3 9h4l5-5v16l-5-5H3z M16 8a6 6 0 0 1 0 8 M18 4a10 10 0 0 1 0 16',
 captions:'M3 5h18v14H3z M10 10a3 3 0 1 0 0 4 M17 10a3 3 0 1 0 0 4',
 keyboard:'M2 6h20v12H2z M5 10h1m3 0h1m3 0h1m3 0h1 M7 14h10',
 send:'M4 12h15m-6-6 6 6-6 6',
 more:'M5 11h1v2H5z M11 11h1v2h-1z M17 11h1v2h-1z',
 close:'M6 6l12 12 M18 6L6 18'
};
document.querySelectorAll('[data-icon]').forEach(i=>{
 i.innerHTML='<svg aria-hidden="true" viewBox="0 0 24 24"><path d="'+paths[i.dataset.icon]+'"/></svg>';
});
let client,mic,clock,start,gesture=0,epoch=0,sound=true,quietMode=false;
const echoMarks=[];
let micAEC='未报告';
const hint=s=>$('#hint').textContent=s;
function idleHint(){return mic?(quietMode?'我在这里，想聊时就开口':'可以直接说话'):'麦克风已关闭'}
function elapsed(){const n=Math.floor((performance.now()-start)/1000);return String(Math.floor(n/60)).padStart(2,'0')+':'+String(n%60).padStart(2,'0')}
function micState(on){$('#micToggle').setAttribute('aria-pressed',String(on));$('#micToggle span').textContent=on?'麦克风开':'麦克风关'}
function mute(){
 gesture++;
 if(mic){mic.stream.getTracks().forEach(t=>t.stop());mic.processor.onaudioprocess=null;mic.processor.disconnect();mic.input.disconnect();mic=null}
 micState(false);
 if(client?.canListen())client.listening(false);
}
function sendAudio(chunks,draft=false,voiceEnd){
 const samples=new Int16Array(chunks.reduce((sum,c)=>sum+c.length,0));
 let offset=0;for(const chunk of chunks){samples.set(chunk,offset);offset+=chunk.length}
 const bytes=new Uint8Array(samples.buffer);let raw='';
 for(let i=0;i<bytes.length;i+=8192)raw+=String.fromCharCode(...bytes.subarray(i,i+8192));
 const audio=btoa(raw);
 if(draft)client.prepareSpeech(audio);else window.submitTurn({audio,phone:true,voiceEnd});
}
async function enableMic(){
 mute();const ticket=gesture;
 try{
  const stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true}});
  if(ticket!==gesture||phone.dataset.phase!=='live'){stream.getTracks().forEach(t=>t.stop());return}
  const ctx=window.callAudioContext,input=ctx.createMediaStreamSource(stream),processor=ctx.createScriptProcessor(1024,1,1);
  const setting=stream.getAudioTracks()[0].getSettings?.().echoCancellation;
  micAEC=setting===true?'已启用':setting===false?'未启用':'浏览器未报告';
  mic={stream,ctx,input,processor};await ctx.resume();
  if(ticket!==gesture)return;
  let pre=[],frames=[],speaking=false,quiet=0,voiced=0,lastVoice=0,onset=0,voiceEnd=0,noise=.003;
  function reset(){pre=[];frames=[];speaking=false;quiet=0;voiced=0;lastVoice=0;onset=0}
  const feed=micBlocks(ctx.sampleRate,(data,endTime)=>{
   if(ticket!==gesture)return;
   let power=0;for(const v of data)power+=v*v;
   const level=Math.sqrt(power/data.length);
   phone.style.setProperty('--voice-level',String(Math.min(1.4,.4+level*8)));
   const pcm=Int16Array.from(data,v=>Math.max(-32768,Math.min(32767,Math.round(v*32767))));
   const busy=!client.canListen(), threshold=Math.max(busy ? .018 : .014,noise*3);
   const echo=sound && level>.007 && client.farEnd.matches(data,endTime);
   if(echo)pcm.fill(0);
   const detected=!echo && level>(speaking?Math.max(.009,noise*1.8):threshold);
   const blockEnd=performance.now()-(ctx.currentTime-endTime)*1000;
   if(!speaking){
    pre.push(pcm);if(pre.length>4)pre.shift();
    if(!detected){onset=0;if(!busy&&!echo&&level<.014)noise=.97*noise+.03*level;return}
    if(++onset<(busy?3:2))return;
    if(busy)window.stopTurn('voice');
    speaking=true;frames=pre;pre=[];voiced=onset;lastVoice=frames.length;voiceEnd=blockEnd;client.listening(true);hint('正在听你说…');
   }else{
    frames.push(pcm);
    if(detected && quiet>=2)client.discardDraft();
    if(detected){quiet=0;voiced++;lastVoice=frames.length;voiceEnd=blockEnd}else quiet++;
   }
   const end=lastVoice+1;
   if(quiet===2&&voiced>=3)sendAudio(frames.slice(0,end),true);
   // Keep ordinary pauses inside a question: the comma fixture reaches 832 ms.
   // ASR still starts after 128 ms; only committing the turn waits for 960 ms.
   if(quiet>=15||frames.length>=420){
    if(voiced>=3){hint(callName+'想一想');sendAudio(frames.slice(0,end),false,voiceEnd)}else{client.listening(false);hint(idleHint())}
    reset();
   }
  });
  processor.onaudioprocess=e=>feed(e.inputBuffer.getChannelData(0),ctx.currentTime-e.inputBuffer.duration);
  input.connect(processor);processor.connect(ctx.destination);
  micState(true);hint(idleHint());
 }catch(err){if(ticket===gesture){mute();hint('麦克风未开启，可点键盘交流')}}
}
function endCall(message){
 const wasLive=phone.dataset.phase==='live';epoch++;mute();clearInterval(clock);
 $('#panel').close();
 if(client)client.closeDialogue();else window.callAudioContext?.close().catch(()=>{});phone.dataset.phase='ended';
 $('#callState').textContent=message||(wasLive?'通话结束 · '+elapsed():'已拒绝来电');$('#accept').disabled=false;$('#review').hidden=!wasLive;
}
async function accept(){
 $('#accept').disabled=true;const ticket=++epoch;$('#callState').textContent='正在接通…';
 // Unlock playback in the actual click on browsers that require a user gesture.
 window.callAudioContext=new AudioContext();await window.callAudioContext.resume().catch(()=>{});
 try{
  client=await import('/client.js');
  if(ticket!==epoch){client.closeDialogue();return}
  await client.resumeAudio();start=performance.now();phone.dataset.phase='live';
  $('#timer').textContent='00:00';clock=setInterval(()=>$('#timer').textContent=elapsed(),500);
  enableMic();
 }catch(err){if(ticket===epoch)endCall('连接未成功，请重试')}

}
$('#accept').onclick=accept;$('#decline').onclick=()=>endCall('已拒绝来电');$('#hang').onclick=()=>endCall();
$('#redial').onclick=()=>location.reload();
$('#micToggle').onclick=()=>{if(mic){mute();hint('麦克风已关闭')}else enableMic()};
$('#speaker').onclick=()=>{sound=!sound;client.speaker(sound);$('#speaker').setAttribute('aria-pressed',sound);$('#speaker span').textContent=sound?'扬声器':'已静音'};
$('#keyboard').onclick=()=>{const f=$('#form');f.hidden=!f.hidden;$('#keyboard').setAttribute('aria-expanded',!f.hidden);if(!f.hidden)$('#text').focus()};
$('#captions').onclick=()=>{const sub=$('#subtitles');sub.hidden=!sub.hidden;$('#captions').setAttribute('aria-pressed',!sub.hidden);$('#captions').setAttribute('aria-label',sub.hidden?'显示字幕':'隐藏字幕')};
$('#takeTurn').onclick=()=>{window.stopTurn();hint(mic?'你说，我在听':'可以打开麦克风，或用键盘交流')};
function review(){
 const box=$('#conversation'),rows=(window.turnLogs||[]),voiced=rows.filter(r=>r.source==='语音');
 const measured=voiced.filter(r=>Number.isFinite(r.replyMs)),within=measured.filter(r=>r.replyMs<=3000);
 $('#summary').textContent='语音 '+voiced.length+' 轮 · 3 秒内 '+within.length+'/'+measured.length+' 个可测轮次 · 语音打断 '+rows.filter(r=>r.interruption==='voice').length+' 次 · 回声标记 '+echoMarks.length+' 次。回声消除：'+micAEC+'。';
 $('#markEcho').hidden=phone.dataset.phase!=='live';
 if(window.motionStats){
  const m=window.motionStats,rate=m.playedMs?Math.round(m.shown*10000/m.playedMs)/10:'—';
  $('#summary').textContent+=' 动画：片内 '+rate+' 帧/秒，浏览器报告掉帧 '+m.dropped+'/'+m.total+'，切片等待下载 '+(m.assetWaitMs/1000).toFixed(2)+' 秒，最长切换 '+Math.round(m.cutMaxMs)+' 毫秒。';
 }
 box.replaceChildren();
 if(!rows.length){const p=document.createElement('p');p.className='empty';p.textContent='聊过的话，会留在这里。';box.append(p)}
 for(const r of rows)for(const [name,text,reply] of [['我',r.text,false],[callName,r.reply,true]]){
  const item=document.createElement('div'),label=document.createElement('small'),p=document.createElement('p');
  item.className='message'+(reply?' reply':'');label.textContent=name+(reply?' · '+roundStatus(r):'');p.textContent=text||(reply?'尚无回复':'未获得转写');item.append(label,p);box.append(item);
 }
 $('#panel').showModal();box.scrollTop=box.scrollHeight;
}
function roundStatus(r){
 const timing=Number.isFinite(r.replyMs)?(r.replyMs/1000).toFixed(2)+' 秒':r.source!=='语音'?'文字输入':r.mutedAtOnset?'扬声器已静音':r.error?'本轮失败':'未测到首声';
 return timing+(r.interruption==='voice'?' · 开口打断':r.interruption?' · 手动打断':'');
}
$('#more').onclick=review;$('#review').onclick=review;
$('#markEcho').onclick=()=>{echoMarks.push(elapsed());review()};
$('#copyResults').onclick=async()=>{
 const text=[$('#summary').textContent,...(window.turnLogs||[]).map((r,i)=>(i+1)+'. '+(r.text||'未转写')+' → '+(r.reply||'未回复')+' ｜ '+roundStatus(r)),'听见回声的时间：'+(echoMarks.join('、')||'未标记')].join('\n');
 try{await navigator.clipboard.writeText(text);$('#copyResults').textContent='已复制'}catch{const out=$('#copyText');out.hidden=false;out.value=text;out.select()}
};
$('#closePanel').onclick=()=>$('#panel').close();
$('#panel').addEventListener('click',e=>{if(e.target===$('#panel')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close()}});
document.querySelectorAll('[data-say]').forEach(b=>b.onclick=()=>{$('#panel').close();window.submitTurn({text:b.dataset.say,phone:true})});
window.addEventListener('dialogue-state',e=>{
 phone.dataset.activity=e.detail.stage;
 $('#takeTurn').hidden=!['thinking','speaking'].includes(e.detail.stage);
 if(e.detail.stage==='thinking')hint(callName+'想一想');
 else if(e.detail.stage==='listening')hint('正在听你说…');
 else if(e.detail.stage==='speaking')hint(callName+'正在说话');
 else hint(idleHint());
});
window.addEventListener('dialogue-mode',e=>{
 quietMode=e.detail==='quiet';$('#modeLabel').textContent=quietMode?'安静陪伴':'陪你聊聊';
 const q=$('#quiet');q.dataset.say=quietMode?'继续聊吧':'安静陪我一会儿';q.innerHTML=quietMode?'继续聊聊 <span>↗</span>':'安静陪伴 <span>☾</span>';
});
new MutationObserver(()=>{
 if(phone.dataset.phase!=='live')return;
 const s=$('#status').textContent;
 if(s.includes('正在回答'))hint(callName+'正在说话');
 else if(s==='等你接着说')hint(idleHint());
 else if(s.includes('未完成'))hint(s);
}).observe($('#status'),{subtree:true,childList:true});
window.addEventListener('dialogue-disconnect',()=>endCall('连接已断开'));
window.addEventListener('pagehide',()=>{epoch++;mute();clearInterval(clock)});
