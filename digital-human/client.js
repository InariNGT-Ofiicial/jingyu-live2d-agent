import {createMotionPlayer} from '/motions/phone/motion-player.js';
import {PlaybackReference} from '/motions/phone/duplex.js';
export const farEnd=new PlaybackReference();
const $=s=>document.querySelector(s),ctx=window.callAudioContext||new AudioContext(),meter=ctx.createAnalyser(),samples=new Float32Array(512);
let closed=false;
const output=ctx.createGain();
meter.fftSize=512;meter.connect(output);output.connect(ctx.destination);
const config=await (await fetch('/config')).json(), bank=new Map(), fetching=new Map();
async function clip(key){
 if(bank.has(key)){
  const buffer=bank.get(key);bank.delete(key);bank.set(key,buffer);return buffer;
 }
 if(fetching.has(key))return fetching.get(key);
 const request=loadClip(key);
 fetching.set(key,request);
 try{return await request}finally{fetching.delete(key)}
}
async function loadClip(key){
 const version=config.audioHashes?.[key];
 const response=await fetch('/audio/'+encodeURIComponent(key)+'.wav'+(version?'?v='+version:''));
 if(!response.ok)throw Error('预设录音不可用：'+key);
 const buffer=await ctx.decodeAudioData(await response.arrayBuffer());
 bank.set(key,buffer);
 if(bank.size>32)bank.delete(bank.keys().next().value);
 return buffer;
}
const portrait=Boolean($('#phone'));
const motion=await createMotionPlayer($('#figure'),portrait,msg=>state(msg));
const director=motion.director;
if(!portrait)await Promise.all(config.audio.slice(0,16).map(clip));
const ws=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/ws');await new Promise((ok,fail)=>{ws.onopen=ok;ws.onerror=fail});
window.addEventListener('pagehide',()=>ws.close(1000,'leaving stage'),{once:true});
$('#source').textContent=config.jev?'预设库 · Jev 可用':'预设库 · 本地选择';
let seq=0,active=null,rec=null,listeningSince=null;
let draftAudio=null,draftKey=0;
const logs=window.turnLogs=[];
function state(t){$('#status').textContent=t}
function activity(stage){director.setState(stage);window.dispatchEvent(new CustomEvent('dialogue-state',{detail:{stage}}))}
function clear(){if(!active)return;active.cancelled=performance.now();farEnd.stop(ctx.currentTime);for(const n of active.nodes){try{n.stop()}catch{}n.disconnect()}active=null}
function spokenChars(){return active?.parts?.filter(p=>p.at<=ctx.currentTime).at(-1)?.chars}
function stop(reason='button'){const heardPrevious=Boolean(active?.heard),chars=spokenChars();if(active)active.interruption=reason;clear();draftAudio=null;listeningSince=null;++seq;ws.send(JSON.stringify({type:'stop',id:seq,heardPrevious,spokenChars:chars}));director.cancel();activity('idle');state('已打断');$('#answer').textContent='';$('#timing').textContent=''}
async function submit(data){
 if(closed||ws.readyState!==WebSocket.OPEN)return;
 await ctx.resume();const heardPrevious=Boolean(active?.heard),chars=spokenChars();clear();const r=active={id:++seq,at:performance.now(),nodes:new Set(),end:0,source:data.audio?'语音':'弹幕',viewer:data.viewer||$('#viewer').value};
 r.voiceEnd=data.voiceEnd;const {voiceEnd,...payload}=data;
 if(payload.audio && payload.audio===draftAudio){delete payload.audio;payload.draftKey=draftKey}
 if(portrait && location.protocol==='https:')payload.compactOutput=Boolean(document.createElement('audio').canPlayType('audio/mpeg'));
 draftAudio=null;
 r.inputStarted=data.audio ? listeningSince ?? r.at : r.at;listeningSince=null;
 logs.push(r);if(portrait&&logs.length>128)logs.shift();
 $('#timing').textContent='';$('#answer').textContent='';$('#question').textContent=data.text||'正在听清你的话…';state('正在听');director.cancel();activity('thinking');
 ws.send(JSON.stringify({...payload,viewer:r.viewer,type:'turn',id:r.id,heardPrevious,spokenChars:chars,segmentedAudio:portrait}));return r.id;
}
window.submitTurn=submit;window.stopTurn=stop;
export function prepareSpeech(audio){
 if(!closed&&!active&&ws.readyState===WebSocket.OPEN){
  draftAudio=audio;ws.send(JSON.stringify({type:'draft',id:seq+1,audio,draftKey:++draftKey,viewer:$('#viewer').value,phone:portrait}));
 }
}
export function discardDraft(){
 if(draftAudio && ws.readyState===WebSocket.OPEN)ws.send(JSON.stringify({type:'continued',id:seq+1,draftKey}));
 draftAudio=null;
}
function finish(r){
 if(active!==r||!r.complete||r.nodes.size)return;
 r.done=performance.now();ws.send(JSON.stringify({type:'played',id:r.id}));active=null;activity('idle');state('等你接着说');
 const li=document.createElement('li');li.textContent=r.viewer+' · '+r.text+'　→　'+r.reply;$('#history').prepend(li);
 while($('#history').children.length>3)$('#history').lastChild.remove();
}
function schedule(r,buf,latency,chars){
 const n=ctx.createBufferSource();n.buffer=buf;n.connect(meter);r.nodes.add(n);
 const at=Math.max(r.end,ctx.currentTime+latency);if(r.end&&at-r.end>.02)(r.gaps??=[]).push(Math.round((at-r.end)*1000));
 if(chars)(r.parts??=[]).push({at,chars,seconds:buf.duration});
 if(!r.scheduledAt){r.scheduledAt=performance.now();r.audioStart=at;r.audioState=ctx.state}
 if(portrait)farEnd.add(buf.getChannelData(0),buf.sampleRate,at);
 r.end=at+buf.duration;n.onended=()=>{r.nodes.delete(n);n.disconnect();finish(r)};n.start(at);
}
function flushSpeech(r){
 if(!r.pending?.length)return;
 if(!r.startedAudio&&!r.complete&&r.buffered<2.0)return;
 r.startedAudio=true;
 for(const buffer of r.pending)schedule(r,buffer,r.end?0:.025);
 r.pending.length=0;
}
ws.onmessage=ev=>{
 const e=JSON.parse(ev.data),r=active;if(!r||r.id!==e.id)return;
 if(e.type==='input'){
  r.input=performance.now();r.text=e.text;$('#question').textContent=r.viewer+' · '+e.text;
  if(!portrait&&/(请|帮我|能不能|可以).{0,5}(读|念).{0,4}弹幕/.test(e.text)){
   motion.warm('read-request');director.request('read-request',{ttl:6500});
  }
  return;
 }
 if(e.route){r.route=e.route;r.selector=e.selector??r.selector;state(e.route)}
 if(e.type==='thinking')return;
 if(e.reply){r.reply=e.reply;$('#answer').textContent=e.reply}
 if(e.type==='cached'){
  r.key=e.key;r.cachedAt=performance.now();r.complete=true;r.route=e.selector==='exact'?'预设直播':'语义选预设';
  const b=e.behavior||{};r.behavior=b;
  if(b.mode){director.setMode(b.mode);window.dispatchEvent(new CustomEvent('dialogue-mode',{detail:b.mode}))}
  const studioGestures={hello:'acknowledge',morning:'acknowledge',thanks:'acknowledge',intro:'read-request',visible:'read-request',goodnight:'acknowledge',present:'read-request',bye:'acknowledge'};
  const gesture=portrait?b.gesture:studioGestures[e.key.split('-')[0]]||b.gesture;
  if(gesture)motion.request(gesture,r.id,r.inputStarted,{explicit:b.explicit,priority:b.explicit?3:1});
  clip(e.key).then(buffer=>{if(active===r){r.clipReady=performance.now();schedule(r,buffer,.02)}}).catch(err=>{if(active===r){r.error=err.message;clear();director.cancel();activity('idle');state(err.message)}});
  return;
 }
 if(e.type==='pcm'){
  if(e.engine)r.engine=e.engine;
  const bytes=Uint8Array.from(atob(e.data),c=>c.charCodeAt(0)),v=new Int16Array(bytes.buffer),b=ctx.createBuffer(1,v.length,24000),a=b.getChannelData(0);
  for(let i=0;i<v.length;i++)a[i]=v[i]/32768;
  (r.chunks??=[]).push({at:performance.now(),seconds:b.duration});
  (r.pending??=[]).push(b);r.buffered=(r.buffered||0)+b.duration;
  if(!r.pcm)r.pcm=performance.now();
  flushSpeech(r);return;
 }
 if(e.type==='voice_part'){
  r.engine=e.engine;r.pcm??=performance.now();
  r.decode=(r.decode||Promise.resolve()).then(async()=>{
   if(active!==r)return;
   const bytes=Uint8Array.from(atob(e.data),c=>c.charCodeAt(0));
   let buffer;
   if(e.codec==='mp3')buffer=await ctx.decodeAudioData(bytes.buffer);
   else{const pcm=new Int16Array(bytes.buffer);buffer=ctx.createBuffer(1,pcm.length,24000);
    const a=buffer.getChannelData(0);for(let i=0;i<pcm.length;i++)a[i]=pcm[i]/32768}
   if(active===r)schedule(r,buffer,r.end?0:.025,e.chars);
  }).catch(()=>{if(active===r){r.error='语音分段解码失败';clear();activity('idle');state(r.error)}});
  return;
 }
 if(e.type==='voice_file'){
  r.engine=e.engine;r.pcm=performance.now();r.complete=true;
  const bytes=Uint8Array.from(atob(e.data),c=>c.charCodeAt(0));
  ctx.decodeAudioData(bytes.buffer).then(buffer=>{if(active===r)schedule(r,buffer,.02)})
   .catch(()=>{if(active===r){r.error='语音解码失败';clear();activity('idle');state(r.error)}});
  return;
 }
 if(e.type==='end'){const end=()=>{if(active===r){r.complete=true;flushSpeech(r);finish(r)}};if(r.decode)r.decode.then(end);else end()}
 if(e.type==='error'){r.error=e.message;clear();director.cancel();activity('idle');state('本轮未完成：'+e.message)}
};
ws.onclose=()=>{clear();state('连接已断开，请刷新重连');if(!closed)window.dispatchEvent(new Event('dialogue-disconnect'))};
setInterval(()=>{const r=active;if(!r||r.heard||!r.nodes.size)return;meter.getFloatTimeDomainData(samples);let power=0;for(const x of samples)power+=x*x;
 if(power/samples.length>.000045){r.heard=performance.now();r.mutedAtOnset=output.gain.value===0;
  if(Number.isFinite(r.voiceEnd)&&!r.mutedAtOnset){
   const stamp=ctx.getOutputTimestamp?.();
   const deviceLag=stamp?.performanceTime ? Math.max(0,Math.min(500,stamp.performanceTime+(ctx.currentTime-stamp.contextTime)*1000-r.heard)) : (ctx.outputLatency||0)*1000;
   r.replyMs=Math.round(r.heard+deviceLag-r.voiceEnd);
  }
  activity('speaking');$('#timing').textContent=Number.isFinite(r.replyMs)?'末音到首声 '+(r.replyMs/1000).toFixed(2)+' 秒':'';state(r.route+' · 正在回答')}
},8);
$('#form').onsubmit=e=>{e.preventDefault();const t=$('#text').value.trim();if(t){$('#text').value='';submit({text:t,phone:portrait})}};
$('#stop').onclick=stop;
$('#mic').onclick=async()=>{
 try{
  if(rec){const m=rec;rec=null;m.stop();return}
  await ctx.resume();const stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true}});
  stop();const m=new MediaRecorder(stream),chunks=[];rec=m;state('录音中');$('#mic').textContent='结束并发送';
  m.ondataavailable=e=>chunks.push(e.data);m.onstop=async()=>{
   stream.getTracks().forEach(t=>t.stop());$('#mic').textContent='开始录音';
   try{const native=await ctx.decodeAudioData(await new Blob(chunks,{type:m.mimeType}).arrayBuffer());
    const off=new OfflineAudioContext(1,Math.ceil(native.duration*16000),16000),s=off.createBufferSource();s.buffer=native;s.connect(off.destination);s.start();
    const x=(await off.startRendering()).getChannelData(0);const pcm=Int16Array.from(x,v=>Math.max(-32768,Math.min(32767,Math.round(v*32767))));let raw='';const bytes=new Uint8Array(pcm.buffer);
    for(let i=0;i<bytes.length;i+=8192)raw+=String.fromCharCode(...bytes.subarray(i,i+8192));await submit({audio:btoa(raw)});
   }catch(err){state('录音处理失败：'+err.message)}
  };m.start();setTimeout(()=>{if(rec===m){rec=null;m.stop()}},29000);
 }catch(err){state('麦克风不可用：'+err.message)}
};
export function speaker(on){output.gain.value=on?1:0}
export function resumeAudio(){return ctx.resume()}
export function canListen(){return !closed&&!active}
export function listening(on){if(!active){listeningSince=on?performance.now():null;activity(on?'listening':'idle')}}
export function socketClosed(){return ws.readyState===WebSocket.CLOSED}
export function closeDialogue(){
 closed=true;clear();ws.close(1000,'call ended');motion.close();
 ctx.close().catch(()=>{});
}
window.dialogueReady=true;state('可以开始对话');
if(portrait && location.protocol!=='https:'){
 // Warm one small recording at a time after connecting. A caller can speak immediately.
 (async()=>{for(const key of config.audio){if(closed)return;try{await clip(key)}catch{return}}})();
}
