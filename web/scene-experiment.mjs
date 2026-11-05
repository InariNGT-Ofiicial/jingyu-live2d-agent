import {installStockingShader,bindOriginalStockings} from './original-stockings.mjs';
import {bindTouchFeedback} from './touch-feedback.mjs';
import {attachChestPhysics} from './idle-events.mjs';
import {bindNaturalMotion} from './natural-motion.mjs';
import {MotionEngine} from './engine.mjs';
import {VoiceStreamPlayer} from './voice-stream-player.mjs';
import {bindDanmaku} from './danmaku-panel.mjs';
import {speechPose} from './speech-performance.mjs';
import {bindMinecraft} from './minecraft-panel.mjs';
const $=s=>document.querySelector(s), clean=new URLSearchParams(location.search).has('clean');
if(clean)document.body.classList.add('clean');
const clientId='studio-'+crypto.randomUUID(),label=$('#state');
$('#client').textContent=clientId;
let ready=false,ctx,buffer,source,analyser,levels,engine,compiled,active=null,generation=0,scene={id:'study-v2',theme:'warm',camera:'wide'},frames=0,lastFrames=0,lastBeat=performance.now(),fps=0;
let streamPlayer=null,streamJobId=null,streamStarting=false,streamEpoch=0,streamMouth=0;
let greetingCues=[];
let streamMessageId=null,streamReceipt=null;
let speechGain,streamPerformance={},lastStreamStats=null;
let stageModel=null;
async function api(path,data){
 const r=await fetch(path,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{});
 const v=await r.json();if(!r.ok)throw Error(v.error||r.statusText);return v;
}
function error(e){$('#error').textContent=e.message||String(e);}
const speechStyles=await api('/data/speech-styles.json');
const presentation=()=>({emotion:$('#speech-emotion').value,intensity:Number($('#speech-intensity').value),motion:$('#speech-motion').checked});
$('#speech-emotion').replaceChildren(...Object.entries(speechStyles).map(([key,s])=>new Option(s.label,key)));
$('#speech-emotion').onchange=()=>{$('#speech-instruction').value='';};
try{$('#speech-volume').value=localStorage.getItem('jingyu-speech-volume')??.8;}catch{}
$('#speech-volume').oninput=()=>{const v=Number($('#speech-volume').value);if(speechGain)speechGain.gain.setTargetAtTime(v,ctx.currentTime,.03);try{localStorage.setItem('jingyu-speech-volume',v);}catch{}};
function clearSpeech(){if(engine){engine.speechPose=null;engine.speechReserved=false;}}
async function audioInit(){
 if(!ctx){ctx=new AudioContext();analyser=ctx.createAnalyser();analyser.fftSize=256;levels=new Uint8Array(analyser.fftSize);speechGain=ctx.createGain();speechGain.gain.value=Number($('#speech-volume').value);analyser.connect(speechGain);speechGain.connect(ctx.destination);}
 await ctx.resume();
 if(!buffer){
  const greeting=await api('/scene-assets/greeting-ds-a3.json');greetingCues=greeting.cues;
  buffer=await ctx.decodeAudioData(await(await fetch('/scene-assets/greeting-ds-a3.wav')).arrayBuffer());
 }
 $('#sound').textContent='声音已启用';
}
function report(job,status,reason){return api('/api/studio/report',{clientId,jobId:job.id,status,error:reason}).catch(error);}
function elapsed(){return active?(active.audio!=='silent'?ctx.currentTime-active.started:(performance.now()-active.started)/1000):0;}
function stop(status='interrupted'){
 stopStream();
 generation++;
 if(source){source.stop();source.disconnect();source=null;}
 if(active)report(active,status);
 active=null;engine?.stop();$('#caption').textContent='';label.textContent='待机';
}
function applyScene(value){
 scene=value;
 const gaming=scene.id==='minecraft';$('#stage').classList.toggle('game-scene',gaming);
 $('.heading h1').textContent=gaming?'DS 娘 · Minecraft':'雨夜书房';
 if(stageModel){stageModel.scale.set((gaming?650:1133)/stageModel.internalModel.originalHeight);stageModel.position.set(gaming?1110:650,gaming?35:20);}
 const base=scene.id==='study-v2'?'scene-assets/study-v2/':'scene-assets/';
 $('#bg').src=base+scene.theme+'-background.png';$('#fg').src=base+scene.theme+'-foreground.png';
 $('#world').style.transform='scale('+(scene.camera==='close'?1.13:1)+')';
 for(const [id,key] of [['#scene','id'],['#theme','theme'],['#camera','camera']])$(id).value=scene[key];
}
const seen=new Set();
async function receive(job){
 if(seen.has(job.id))return;
 seen.add(job.id);if(seen.size>100)seen.delete(seen.values().next().value);
 if(job.action==='set'){applyScene(job.scene);await report(job,'completed');return;}
 if(job.clientId!==clientId)return;
 $('#receipt').textContent=job.id+' · 已受理';
 if(job.action==='stop'){stop();await report(job,'completed');$('#receipt').textContent=job.id+' · 已停止';return;}
 if(job.action==='speak'){await startStream(false,job.speech,null,job);return;}
 stop();const token=generation;
 try{
  let speechBuffer=buffer;
  if(job.audio!=='silent'){
   if(!ctx||ctx.state!=='running'||!buffer)throw Error('请先点击「启用声音」，再通过接口播放');
   if(job.audio==='speech')speechBuffer=await ctx.decodeAudioData(await(await fetch(job.speech.audioUrl)).arrayBuffer());
  }
  if(token!==generation)return;
  const plan=job.compiled||(job.audio==='speech'?{duration:0,tracks:[],steps:[]}:compiled);
  active={...job,started:job.audio!=='silent'?ctx.currentTime:performance.now(),duration:Math.max(plan.duration,job.audio!=='silent'?speechBuffer.duration:0)};
  if(job.audio!=='silent'){source=ctx.createBufferSource();source.buffer=speechBuffer;source.connect(analyser);source.start();}
  if(plan.tracks.length)engine.start({id:job.id,compiled:plan});
  engine.speechReserved=job.audio!=='silent';label.textContent='正在表演';
  if(job.audio==='speech')$('#caption').textContent=job.speech.text;
  await report(job,'playing');$('#receipt').textContent=job.id+' · 执行中';
 }catch(e){if(token!==generation)return;stop();await report(job,'error',e.message);error(e);}
}
async function command(data){return api('/api/studio/command',{clientId,...data});}
window.sceneExperiment={status:()=>({ready,playing:!!active||!!streamPlayer?.active,time:active?elapsed():streamPlayer?.status().time||0,paused:!active&&!streamPlayer?.active,motionActive:!!engine?.job||!!engine?.speechPose,fps,theme:scene.theme,clientId,audioReady:ctx?.state==='running'}),play:async()=>{await audioInit();return command({action:'play'});},stop:()=>command({action:'stop'})};
function stopStream(){
 if(streamReceipt){report(streamReceipt,'interrupted');streamReceipt=null;}
 if(streamPlayer)lastStreamStats=streamPlayer.status();clearSpeech();streamMouth=0;
 streamEpoch++;
 const jid=streamJobId;streamPlayer?.stop();streamPlayer=null;streamJobId=null;streamStarting=false;
 if(jid)api('/api/studio/voice/cancel',{id:jid}).catch(error);
 if(streamMessageId)api('/api/studio/danmaku/report',{id:streamMessageId,clientId,status:'cancelled'}).catch(error);
 streamMessageId=null;
 $('#stream-cancel').disabled=true;$('#stream-play').disabled=false;$('#stream-agent').disabled=false;
 $('#caption').textContent='';
 label.textContent='待机';
}
async function startStream(incremental=false,suppliedJob=null,messageId=null,receipt=null){
 if((streamStarting||streamPlayer?.active)&&!suppliedJob)return;
 stop();const epoch=streamEpoch;streamStarting=true;lastStreamStats=null;const requestedAt=performance.now();
 streamReceipt=receipt;
 if(receipt)report(receipt,'preparing');
 if(engine)engine.speechReserved=true;
 label.textContent='准备说话';
 $('#stream-play').disabled=true;$('#stream-agent').disabled=true;$('#stream-cancel').disabled=false;
 try{
  await audioInit();
  if(epoch!==streamEpoch)return;
  const job=suppliedJob||await api('/api/studio/voice/start',{text:incremental?'':$('#speech-text').value,
   instruction:$('#speech-instruction').value,performance:presentation(),inputComplete:!incremental});
  if(epoch!==streamEpoch){await api('/api/studio/voice/cancel',{id:job.id});return;}
  streamJobId=job.id;
  streamPerformance=job.performance||{emotion:'auto'};
  streamMessageId=messageId;let reportedPlaying=false;
  $('#stream-status').textContent=incremental?'等待 Agent 发送台词 · '+job.id:'正在准备声音，收到音频后自动播放…';
  streamPlayer=new VoiceStreamPlayer(ctx,analyser,stats=>{
   if(epoch!==streamEpoch)return;
   $('#caption').textContent=stats.text;
   if(stats.started)label.textContent='正在说话';
   if(stats.started&&!reportedPlaying){reportedPlaying=true;if(receipt)report(receipt,'playing');if(messageId)api('/api/studio/danmaku/report',{id:messageId,clientId,status:'playing'}).catch(error);}
   if(stats.started)$('#stream-status').textContent='正在说话 · 已播 '+stats.time.toFixed(1)+' 秒 · 缓冲 '+stats.queuedSeconds.toFixed(1)+' 秒'+(stats.underrunBlocks?' · 曾等待后续音频':'');
   $('#speech-metrics').textContent='首包 '+(stats.firstPCMSeconds?.toFixed(2)??'—')+' 秒 · 起播 '+(stats.startPlaybackSeconds?.toFixed(2)??'—')+' 秒 · 等待音频块 '+stats.underrunBlocks;
  },{bufferSeconds:Number($('#speech-buffer').value),requestedAt});
  await streamPlayer.play(job.streamUrl);
  if(epoch!==streamEpoch)return;
  const saved=await api('/api/studio/voice?id='+job.id);
  if(receipt){await report(receipt,saved.status==='ready'?'completed':'error',saved.error);streamReceipt=null;}
  if(messageId)await api('/api/studio/danmaku/report',{id:messageId,clientId,status:saved.status==='ready'?'done':'error',error:saved.error});
  $('#stream-status').textContent=saved.status==='ready'?'播放完成，已保存，可重播或下载':saved.error||'已停止';
  if(saved.status==='ready')await refreshVoices(job.id);
 }catch(e){if(epoch===streamEpoch){if(receipt){await report(receipt,'error',e.message);streamReceipt=null;}$('#stream-status').textContent=e.message;if(streamJobId)await api('/api/studio/voice/cancel',{id:streamJobId}).catch(()=>{});if(messageId)await api('/api/studio/danmaku/report',{id:messageId,clientId,status:'error',error:e.message}).catch(()=>{});}}
 finally{
  if(epoch===streamEpoch){if(streamPlayer)lastStreamStats=streamPlayer.status();streamPlayer?.stop();streamPlayer=null;streamJobId=null;streamMessageId=null;streamStarting=false;clearSpeech();
   $('#caption').textContent='';label.textContent='待机';$('#stream-cancel').disabled=true;$('#stream-play').disabled=false;$('#stream-agent').disabled=false;}
 }
}
window.sceneExperiment.voice={start:startStream,stop:stopStream,status:()=>({last:lastStreamStats,id:streamJobId,starting:streamStarting,mouth:streamMouth,performance:engine?.speechPose,...streamPlayer?.status()})};
const danmaku=bindDanmaku({api,clientId,audioInit,stop:stopStream,play:(job,id)=>startStream(false,job,id)});
$('#voice-warmup').onclick=async()=>{
 try{await api('/api/studio/voice/warmup',{});$('#stream-status').textContent='声线加载中，完成后可直接开口…';await refreshVoices();}catch(e){$('#stream-status').textContent=e.message;}
};
$('#stream-play').onclick=()=>startStream(false);
$('#stream-agent').onclick=()=>startStream(true);
$('#stream-cancel').onclick=()=>{stopStream();$('#stream-status').textContent='已停止播放；当前合成片段正在收尾';};
$('#sound').onclick=()=>audioInit().catch(error);
$('#play').onclick=()=>window.sceneExperiment.play().catch(error);
$('#stop').onclick=()=>command({action:'stop'}).catch(error);
let speechId=null;
let savedTakes=[];
function selectTake(){
 const take=savedTakes.find(t=>t.id===$('#voice-history').value);
 speechId=take?.id||null;$('#speech-play').disabled=!speechId;
 $('#voice-download').hidden=!speechId;
 if(take){
  $('#speech-text').value=take.text;$('#speech-instruction').value=take.instruction;
  $('#speech-emotion').value=take.performance?.emotion||'auto';$('#speech-intensity').value=take.performance?.intensity??.65;$('#speech-motion').checked=take.performance?.motion!==false;
  $('#voice-download').href=take.audioUrl;$('#voice-download').download='DS-'+take.id+'.wav';
  $('#voice-status').textContent='已保存 · '+take.duration.toFixed(1)+' 秒 · 可重播';
 }
}
async function refreshVoices(preferred){
 const v=await api('/api/studio/voice');savedTakes=(v.takes||[]).filter(t=>t.status==='ready');
 $('#voice-history').replaceChildren(new Option('选择已生成台词',''),...savedTakes.map(t=>new Option(t.text.slice(0,28)+' · '+t.duration.toFixed(1)+'s',t.id)));
 $('#voice-history').value=preferred||savedTakes[0]?.id||'';selectTake();
 $('#synthesize').disabled=!v.ready||v.running;
 const phase=v.engineState?.status;
 $('#voice-warmup').textContent=phase==='ready'?'声线已常驻':phase==='loading'?'声线加载中…':'加载声线';
 $('#voice-warmup').disabled=phase==='ready'||phase==='loading';
 if(!speechId)$('#voice-status').textContent=v.ready?v.voice+' · '+v.engine:v.error;
 if(v.running||phase==='loading'){if(v.running)$('#voice-status').textContent='后台正在合成，完成后会自动恢复…';setTimeout(()=>refreshVoices().catch(error),1500);}
}
$('#voice-history').onchange=selectTake;
$('#synthesize').onclick=async()=>{
 $('#synthesize').disabled=true;$('#speech-play').disabled=true;speechId=null;
 try{
  stop();await audioInit();
  let job=await api('/api/studio/voice',{text:$('#speech-text').value,instruction:$('#speech-instruction').value,performance:presentation()});
  $('#voice-status').textContent='DS 娘正在合成，首次加载需要一些时间…';
  while(job.status==='synthesizing'){await new Promise(r=>setTimeout(r,1000));job=await api('/api/studio/voice?id='+job.id);}
  if(job.status!=='ready')throw Error(job.error);
  speechId=job.id;$('#speech-play').disabled=false;
  $('#voice-status').textContent='已生成 · '+job.duration.toFixed(1)+' 秒 · 可播放或重播';
  await refreshVoices(job.id);
 }catch(e){$('#voice-status').textContent=e.message;}
 finally{$('#synthesize').disabled=false;}
};
$('#speech-play').onclick=async()=>{try{await audioInit();await command({action:'play',audio:'speech',speechId});}catch(e){error(e);}};
refreshVoices().catch(error);
for(const id of ['#scene','#theme','#camera'])$(id).onchange=()=>command({action:'set',scene:{id:$('#scene').value,theme:$('#theme').value,camera:$('#camera').value}}).catch(error);
async function obs(action){
 $('#obs-status').textContent='正在执行…';
 try{
  const v=await api('/api/studio/obs',{action,scene:$('#obs-scenes').value});
  if(v.scenes){$('#obs-scenes').replaceChildren(...v.scenes.scenes.map(s=>new Option(s.sceneName,s.sceneName)));$('#obs-scenes').value=v.scenes.currentProgramSceneName;}
  $('#obs-status').textContent=v.outputPath?'已保存：'+v.outputPath:v.recording?.outputActive?'录制中':'OBS 已连接 · 未录制';
 }catch(e){$('#obs-status').textContent=e.message;}
}
for(const [id,action]of [['#obs-check','status'],['#obs-switch','switch'],['#obs-record','record'],['#obs-stop','stop']])$(id).onclick=()=>obs(action);
try{
 const app=new PIXI.Application({view:$('canvas'),width:1280,height:720,backgroundAlpha:0,antialias:true});
 app.ticker.maxFPS=60;
 const setStockingShader=installStockingShader(app.renderer.gl);
 const profile=await api('/data/model-profile.json');
 const model=await PIXI.live2d.Live2DModel.from('/model/大肥鱼.model3.json',{autoInteract:false,motionPreload:'NONE'});
 stageModel=model;
 app.stage.addChild(model);model.anchor.set(.5,0);model.scale.set(1133/model.internalModel.originalHeight);model.position.set(650,20);
 compiled=await api('/api/compile',{version:1,actions:[{kind:'look',direction:'left',at:0,duration:2,strength:.35},{kind:'nod',at:2.3,duration:2,strength:.3},{kind:'look',direction:'center',at:4.5,duration:3,strength:.5}]});
 const m=model.internalModel;engine=new MotionEngine(m.coreModel,profile,()=>{});m.eyeBlink=undefined;m.breath=undefined;m.updateFocus=()=>{};
 bindNaturalMotion(engine,$('#stage'));
 attachChestPhysics(m,profile,()=>engine.chestGain,()=>engine.job?null:engine.touchInput);
 bindOriginalStockings({model,stage:$('#stage'),canvas:$('canvas'),renderer:app.renderer,setShaderProgress:setStockingShader,busy:()=>!!active||!!engine.job||!!engine.speechReserved,occluded:e=>scene.id!=='minecraft'&&e.clientY>$('#stage').getBoundingClientRect().top+$('#stage').clientHeight*.82});
 bindTouchFeedback({stage:$('#stage'),canvas:$('canvas'),renderer:app.renderer,model,engine,busy:()=>!!active||!!engine.job||!!engine.speechReserved,play:plan=>command({action:'play',audio:'silent',plan}),occluded:e=>e.clientY>$('#stage').getBoundingClientRect().top+$('#stage').clientHeight*.82});
 bindMinecraft({api,clientId,engine,stage:$('#stage'),game:$('#minecraft-view'),command});
 let last=performance.now();
 m.updateNaturalMovements=()=>{
  // Share the laptop GPU with TTS; restore 60 FPS once synthesis has finished.
  app.ticker.maxFPS=streamPlayer?.active&&!streamPlayer.finished?30:60;
  const now=performance.now(),dt=now-last;last=now;frames++;
  const stream=streamPlayer?.status();let speechCaption='';
  engine.speechPose=stream?.started?speechPose(speechStyles,{...stream,performance:streamPerformance}):null;
  if(active?.audio==='speech'){
   const t=elapsed(),speech=active.speech,segments=speech.segments?.length?speech.segments:[{text:speech.text,offsetSamples:0}],rate=speech.sampleRate||24000;
   const index=Math.max(0,segments.findLastIndex(s=>s.offsetSamples/rate<=t)),segment=segments[index];
   speechCaption=segment.text;
   engine.speechPose=speechPose(speechStyles,{text:segment.text,time:t,segmentTime:t-segment.offsetSamples/rate,segmentIndex:index,performance:speech.performance||{},duration:speech.duration});
  }
  if(active)engine.elapsed=Math.max(0,elapsed()-Math.min(dt/1000,1));
  engine.tick(dt);
  let mouth=0;
  if(streamPlayer?.active){
   analyser.getByteTimeDomainData(levels);mouth=Math.min(1,Math.sqrt(levels.reduce((v,n)=>v+((n-128)/128)**2,0)/levels.length)*5);
  }
  streamMouth=streamPlayer?.active?mouth:0;
  if(active){
   if(active.audio!=='silent'){
    analyser.getByteTimeDomainData(levels);mouth=Math.min(1,Math.sqrt(levels.reduce((v,n)=>v+((n-128)/128)**2,0)/levels.length)*5);
    const t=elapsed();$('#caption').textContent=active.audio==='speech'?speechCaption:greetingCues.find(c=>t>=c.start&&t<c.end)?.text||'';
   }
   if(elapsed()>=active.duration){const id=active.id;stop('completed');$('#receipt').textContent=id+' · 已完成';}
  }
  if((!active||active.audio!=='silent')&&m.coreModel.getParameterIndex('ParamMouthOpenY')>=0)m.coreModel.setParameterValueById('ParamMouthOpenY',mouth);
 };
 ready=true;
 async function heartbeat(){
  const now=performance.now();fps=Math.round((frames-lastFrames)*1000/Math.max(1,now-lastBeat));lastFrames=frames;lastBeat=now;
  $('#telemetry').textContent=fps+' FPS · 1280 × 720';
  await api('/api/studio/heartbeat',{clientId,ready,presentation:clean?'obs':'web',telemetry:{fps,playing:!!active||!!streamPlayer?.active,audioTime:active?elapsed():streamPlayer?.status().time||0,jobId:active?.id||streamReceipt?.id,audioReady:ctx?.state==='running'}});
 }
 setInterval(()=>{if(active&&elapsed()>=active.duration){const id=active.id;stop('completed');$('#receipt').textContent=id+' · 已完成';}},100);
 const state=await api('/api/state');
 await heartbeat();
 const events=new EventSource('/api/events?after='+state.seq);
 events.addEventListener('studio-command',e=>receive(JSON.parse(e.data)).catch(error));
 events.addEventListener('danmaku',e=>danmaku.update(JSON.parse(e.data)));
 events.addEventListener('danmaku-speech',e=>danmaku.receive(JSON.parse(e.data)));
 events.addEventListener('danmaku-stop',e=>{if(JSON.parse(e.data).clientId===clientId)stopStream();});
 events.onopen=()=>api('/api/studio/state').then(s=>applyScene(s.scene)).catch(error);
 applyScene((await api('/api/studio/state')).scene);
 setInterval(()=>heartbeat().catch(error),2000);
 $('#play').disabled=false;label.textContent='待机';
 window.addEventListener('pagehide',()=>{stop();events.close();});
}catch(e){error(e);label.textContent='加载失败';window.sceneExperiment.error=e.message;}
