import {MotionEngine} from './engine.mjs';
import {StressRunner} from './stress.mjs';
import {FrameExporter} from './exporter.mjs';
import {savePresetDialog} from './presets-ui.mjs';
const $=id=>document.getElementById(id);
const clientId=crypto.randomUUID();
const comparisonMode=new URLSearchParams(location.search).get('comparison')==='1';
let comparisonActive=comparisonMode;
let engine,model,pixi,physics,profile,demos,currentJob,lastJob,view='portrait',ready=false,pendingJob,state,events,stress;
let lastHeartbeat=0,lastReport=0,lastUI=0,lastFrames=0,lastFpsTime=performance.now(),fps=0;
let toastTimer;
let backend='web',exportId=null,exportPoll=null;
const exporter=new FrameExporter({api,clientId,onProgress:showExport,getRenderer:()=>pixi?.renderer});
function showExport(job,message){
  exportId=job.id;$('export-status').textContent=message||({queued:'等待渲染',rendering:'正在渲染',compiling:'正在编译 VTS 动作',deploying:'正在部署 VTS 动作',recording:'正在采集 VTS 原生画面',cancelling:'正在停止录制并恢复 VTS',encoding:'正在编码',completed:'导出完成',cancelled:'已取消',error:job.error}[job.status]||job.status);
  if(!['completed','error','cancelled'].includes(job.status)){$('export-button').disabled=true;$('export-download').hidden=true;}
  $('export-progress').value=job.progress||0;$('export-cancel').disabled=['completed','error','cancelled'].includes(job.status);
  if(job.status==='completed'){$('export-download').href=job.url;$('export-download').download=`jingyu-${job.id}.${job.format}`;$('export-download').hidden=false;}
  if(['completed','error','cancelled'].includes(job.status)){clearInterval(exportPoll);exportPoll=null;$('export-button').disabled=false;}
}
function applyBackend(value){
  backend=value;$('backend-select').value=value;
  $('backend-note').textContent=value==='vts'?'动作在 VTube Studio 窗口播放；此处保留网页待机预览。':'动作在当前网页舞台播放。';
  for(const id of ['idle-toggle','physics-toggle','gaze-toggle','strength'])$(id).disabled=value==='vts';
  if(value==='vts')$('pause').disabled=true;
}
function backendJob(job){
  lastJob=job;renderPlan(job);$('pause').disabled=true;
  const labels={queued:'等待 VTS',compiling:'正在编译原生动作',deploying:'正在热部署到 VTS',playing:'VTS 正在播放',stopping:'正在停止 VTS',completed:'VTS 表演已完成',interrupted:'VTS 已停止并恢复',error:job.error||'VTS 执行失败'};
  setExecution(labels[job.status]||job.status);$('model-state').textContent=labels[job.status]||job.status;$('progress').style.width=`${(job.progress||0)*100}%`;
  $('playback-label').textContent=`VTS · ${job.compiled.sourcePlan.title||job.compiled.intent}`;
  $('time-label').textContent=`${timeLabel(job.status==='completed'?job.compiled.duration:(job.vts?.elapsed||0))} / ${timeLabel(job.compiled.duration)}`;
}
function toast(message){$('toast').textContent=message;$('toast').classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').classList.remove('show'),3500);}
async function api(path,data){
  const response=await fetch(path,{method:data===undefined?'GET':'POST',headers:data===undefined?{}:{'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data)});
  const value=await response.json();if(!response.ok)throw new Error(value.error||`HTTP ${response.status}`);return value;
}
function bridgeOnline(value){$('connection-dot').classList.toggle('online',value);$('bridge-status').textContent=value?'本地桥已连接':'本地桥连接中断';}
function timeLabel(s){return `${String(Math.floor(s/60)).padStart(2,'0')}:${s%60<10?'0':''}${Math.floor(s%60)}`;}
function renderInbox(items){
  const pending=items.filter(x=>x.status==='pending');$('inbox-count').textContent=`${pending.length} 条待处理`;
  const list=$('inbox-list');list.replaceChildren();
  if(!items.length){const p=document.createElement('p');p.className='muted';p.textContent='你的自由文本会出现在这里。';list.append(p);return;}
  for(const item of items.slice(0,8)){
    const box=document.createElement('div');box.className='inbox-item';
    const header=document.createElement('header');const id=document.createElement('span');id.textContent=`#${item.id}`;
    const status=document.createElement('span');status.textContent={pending:'等待 Codex',compiled:'已编译',declined:'能力受限'}[item.status]||item.status;
    header.append(id,status);const text=document.createElement('div');text.textContent=item.prompt;box.append(header,text);
    if(item.reason){const reason=document.createElement('small');reason.textContent=item.reason;box.append(reason);}list.append(box);
  }
}
function renderPlan(job){
  $('save-current-preset').disabled=false;
  $('save-current-preset').onclick=()=>savePresetDialog(job.compiled.sourcePlan);
  $('replay-current').disabled=['queued','compiling','deploying','playing','stopping'].includes(job.status);
  $('replay-current').onclick=async()=>{try{await api('/api/replay',{jobId:job.id,backend:$('backend-select').value});}catch(e){toast(e.message);}};
  const c=job.compiled;$('source-badge').textContent=job.source==='Codex'?'Codex 编排':job.source||'动作示例';
  $('plan-summary').textContent=c.summary||c.intent;$('compiled-json').textContent=JSON.stringify(c.sourcePlan,null,2);
  const list=$('score-steps');list.replaceChildren();
  for(const step of c.steps){
    const el=document.createElement('div');el.className='score-step';el.dataset.index=step.index;
    const dot=document.createElement('span');dot.className='step-dot';dot.textContent=String(step.index+1).padStart(2,'0');
    const title=document.createElement('span');title.textContent=step.label;
    const time=document.createElement('span');time.className='step-time';time.textContent=`${step.start.toFixed(1)}s — ${(step.start+step.duration).toFixed(1)}s`;
    el.append(dot,title,time);list.append(el);
  }
  $('warnings').hidden=!c.warnings.length;$('warnings').textContent=c.warnings.join('；');
  $('playback-label').textContent=c.sourcePlan.title||c.summary||'Codex 动作计划';
}
function setExecution(text){$('execution-status').querySelector('span').textContent=text;}
async function report(status,job,error=''){
  if(!job)return;
  try{await api('/api/report',{clientId,jobId:job.id,status,progress:status==='completed'?1:Math.min(1,(engine?.elapsed||0)/job.compiled.duration),error});}
  catch(e){bridgeOnline(false);}
}
function receive(job){
  if(job.backend==='vts'){backendJob(job);return;}
  if(!['queued','playing'].includes(job.status))return;
  if(engine?.job?.id===job.id)return;
  if(!ready){pendingJob=job;return;}
  try{
    comparisonActive=comparisonMode||job.compiled.sourcePlan.comparison===true;
    if(comparisonActive){engine.clock=0;engine.current.clear();engine.gaze=null;engine.amplitude=1;engine.idle=true;}
    engine.start(job);
  }catch(error){report('error',job,error.message);toast(error.message);return;}
  currentJob=job;lastJob=job;renderPlan(job);$('pause').disabled=false;$('pause').textContent='Ⅱ';$('pause').setAttribute('aria-label','暂停动作');
  if(['full','portrait'].includes(job.compiled.sourcePlan.view)){
    view=job.compiled.sourcePlan.view;document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===view)));resize();
  }
  $('stage-caption').textContent=job.compiled.intent||'正在执行动作计划';$('model-state').textContent='动作中';
  for(const b of document.querySelectorAll('[data-demo]'))b.classList.toggle('active',demos[b.dataset.demo]?.title===job.compiled.sourcePlan.title);
}
function stopLocal(){
  $('replay-current').disabled=!lastJob;
  stress?.cancel();
  engine?.stop();currentJob=null;pendingJob=null;$('pause').disabled=true;$('pause').textContent='Ⅱ';$('model-state').textContent=ready?'自然待机':'加载中';
  $('stage-caption').textContent='呼吸、眨眼与细微摆动 · 自然待机';$('progress').style.width='0%';setExecution('已停止，正在平滑回到待机');
  document.querySelectorAll('.score-step').forEach(e=>e.classList.remove('active'));
}
function connectEvents(after){
  events=new EventSource(`/api/events?after=${after}`);
  events.onopen=()=>bridgeOnline(true);events.onerror=()=>bridgeOnline(false);
  events.addEventListener('execute',e=>receive(JSON.parse(e.data)));
  events.addEventListener('backend-job',e=>backendJob(JSON.parse(e.data)));
  events.addEventListener('backend',e=>applyBackend(JSON.parse(e.data).backend));
  events.addEventListener('export',e=>exporter.run(JSON.parse(e.data)));
  events.addEventListener('export-status',e=>{const j=JSON.parse(e.data);if(j.id===exportId){if(j.status==='cancelled')exporter.active=null;showExport(j);}});
  events.addEventListener('stop',()=>stopLocal());
  events.addEventListener('lab',e=>stress?.run(JSON.parse(e.data)));
  events.addEventListener('inbox',async()=>{try{const data=await api('/api/inbox');renderInbox(data.requests);}catch{}});
}
function resize(){
  if(!model||!pixi)return;const s=$('scene'),w=s.clientWidth,h=s.clientHeight;pixi.renderer.resize(w,h);
  const fit=Math.min(w*.9/model.internalModel.originalWidth,h*.95/model.internalModel.originalHeight);
  model.scale.set(fit*(view==='portrait'?1.62:1));model.anchor.set(.5,0);model.position.set(w/2,h*(view==='portrait'?-.035:.025));
}
function updateUI(){
  if(!engine)return;const now=performance.now();if(now-lastUI<100)return;lastUI=now;
  const job=engine.job,t=engine.elapsed,duration=job?.compiled.duration||lastJob?.compiled.duration||0;
  if(job){
    $('time-label').textContent=`${timeLabel(t)} / ${timeLabel(duration)}`;$('progress').style.width=`${Math.min(100,t/duration*100)}%`;
    for(const el of document.querySelectorAll('.score-step')){
      const step=job.compiled.steps[Number(el.dataset.index)];el.classList.toggle('active',t>=step.start&&t<step.start+step.duration);el.classList.toggle('done',t>=step.start+step.duration);
    }
  }
  const telem=engine.telemetry();telem.fps=fps;telem.physics=!!model.internalModel.physics;
  telem.exportReady=true;
  if(comparisonActive)telem.values=Object.fromEntries(profile.allParameters.map(p=>[p.id,+model.internalModel.coreModel.getParameterValueById(p.id).toFixed(6)]));
  $('telemetry').textContent=JSON.stringify(telem,null,2);$('scene').dataset.runtime='ready';$('scene').dataset.frames=engine.frames;
  if(now-lastFpsTime>1500){fps=Math.round((engine.frames-lastFrames)*1000/(now-lastFpsTime));lastFrames=engine.frames;lastFpsTime=now;}
  telem.comparisonMode=comparisonActive;
  if(now-lastHeartbeat>(comparisonActive?100:1800)){lastHeartbeat=now;api('/api/heartbeat',{clientId,ready,telemetry:telem}).then(()=>bridgeOnline(true)).catch(()=>bridgeOnline(false));}
  if(job&&now-lastReport>1000){lastReport=now;report('playing',job);}
}
async function loadModel(){
  const canvas=$('model-canvas');
  if(!window.PIXI?.live2d?.Live2DModel||!window.Live2DCubismCore)throw new Error('本地 Live2D 运行库未能加载，请刷新页面。');
  pixi=new PIXI.Application({view:canvas,width:Math.max(1,$('scene').clientWidth),height:Math.max(1,$('scene').clientHeight),backgroundAlpha:0,antialias:true,autoDensity:true,resolution:Math.min(devicePixelRatio||1,1.5),powerPreference:'high-performance'});
  PIXI.live2d.Live2DModel.registerTicker(PIXI.Ticker);
  model=await PIXI.live2d.Live2DModel.from('/model/大肥鱼.model3.json',{autoInteract:false,autoUpdate:true,motionPreload:'NONE'});
  pixi.stage.addChild(model);physics=model.internalModel.physics;
  const core=model.internalModel.coreModel;
  engine=new MotionEngine(core,profile,(status,job)=>{
    if(status==='playing'){setExecution(`舞台正在执行 · ${job.compiled.duration.toFixed(1)} 秒`);report(status,job);}
    if(status==='completed'){
      $('replay-current').disabled=false;
      setExecution('舞台已完成 · 已平滑回到待机');report(status,job);currentJob=null;$('pause').disabled=true;
      $('model-state').textContent='自然待机';$('stage-caption').textContent='动作已完成 · 呼吸与眨眼继续';
      $('progress').style.width='100%';$('time-label').textContent=`${timeLabel(job.compiled.duration)} / ${timeLabel(job.compiled.duration)}`;
      document.querySelectorAll('.score-step').forEach(e=>{e.classList.remove('active');e.classList.add('done');});
    }
  });
  // This hook is called after motion/blink, before author physics and model.update().
  model.internalModel.eyeBlink=undefined;model.internalModel.breath=undefined;model.internalModel.updateFocus=()=>{};
  // Pixi caps ticker delta; a background tab must still follow wall-clock plans.
  let lastMotionTick=performance.now();
  model.internalModel.updateNaturalMovements=()=>{const now=performance.now();engine.tick(now-lastMotionTick);lastMotionTick=now;};
  stress=new StressRunner({model,pixi,engine,profile,clientId,api,
    onStatus:(phase,ratio)=>{setExecution(phase);$('stage-caption').textContent=phase;$('model-state').textContent='隔离压力测试';$('progress').style.width=`${ratio*100}%`;},
    onRestore:()=>{lastMotionTick=performance.now();$('model-state').textContent='自然待机';$('stage-caption').textContent='压力测试结束 · 已恢复自然待机';}});
  model.internalModel.on('beforeModelUpdate',updateUI);
  new ResizeObserver(resize).observe($('scene'));resize();
  ready=true;$('loading').hidden=true;$('model-state').textContent='自然待机';
  $('scene').dataset.ready='true';
  await api('/api/heartbeat',{clientId,ready:true,telemetry:engine.telemetry()});
  if(pendingJob){const job=pendingJob;pendingJob=null;receive(job);}
}
function mountControls(){
  applyBackend(state.backend||'web');
  $('backend-select').onchange=async e=>{const previous=backend;try{const r=await api('/api/backend',{backend:e.target.value});applyBackend(r.backend);}catch(error){applyBackend(previous);toast(error.message);}};
  $('backend-check').onclick=async()=>{try{const r=await api('/api/backends');$('backend-note').textContent=r.vts.available?'VTS API 在线 · 首次连接需在 VTS 允许插件。':r.vts.error;}catch(e){toast(e.message);}};
  $('export-format').onchange=()=>{$('export-background').disabled=$('export-format').value==='gif';};
  $('export-renderer').onchange=()=>{$('export-source-note').textContent=$('export-renderer').value==='vts'?'重播当前计划并采集 VTS Spout 原生画面，沿用 VTS 镜头；请保持 VTS 运行。':'网页渲染器固定步长采样，全身画面。';};
  $('capture-check').onclick=async()=>{try{const c=(await api('/api/export/capabilities')).vts;$('export-status').textContent=c.available?`${c.sender} · ${c.width} × ${c.height} · alpha ${c.alphaRange.join('–')}`:c.error||'VTS Spout 未就绪';}catch(e){toast(e.message);}};
  $('export-button').onclick=async()=>{
    $('export-button').disabled=true;$('export-download').hidden=true;
    try{const [width,height]=$('export-size').value.split('x').map(Number);const job=await api('/api/export',{clientId,renderer:$('export-renderer').value,sender:$('export-sender').value.trim(),format:$('export-format').value,width,height,fps:Number($('export-fps').value),background:$('export-background').value});showExport(job);clearInterval(exportPoll);exportPoll=setInterval(async()=>{try{showExport(await api(`/api/export?id=${job.id}`));}catch(e){clearInterval(exportPoll);$('export-button').disabled=false;toast(e.message);}},1000);}
    catch(e){$('export-button').disabled=false;toast(e.message);}
  };
  $('export-cancel').onclick=async()=>{if(exportId)try{showExport(await api('/api/export/cancel',{id:exportId}));}catch(e){toast(e.message);}};
  const icons={hello:'✧',curious:'⌕',shy:'◡',explain:'☝',no:'↔',thanks:'♡'};
  const captions={hello:'注视 · 微笑 · 点头',curious:'视线先行 · 歪头',shy:'低头 · 脸红 · 眨眼',explain:'原生手势 · 讲解口型',no:'小幅摇头 · 眉眼',thanks:'抚胸 · 微笑 · 点头'};
  for(const [id,demo]of Object.entries(demos)){
    const button=document.createElement('button');button.className='demo-button';button.dataset.demo=id;
    const icon=document.createElement('span');icon.className='demo-icon';icon.textContent=demo.icon||icons[id];const text=document.createElement('span');
    const title=document.createElement('strong');title.textContent=demo.title;const small=document.createElement('small');small.textContent=demo.caption||captions[id];text.append(title,small);
    const arrow=document.createElement('span');arrow.className='demo-arrow';arrow.textContent='↗';button.append(icon,text,arrow);
    button.onclick=async()=>{if(!ready){toast('模型还在加载，请稍等一下。');return;}try{await api('/api/demo',{name:id});}catch(e){toast(e.message);}};
    $(demo.group==='expressive'?'expressive-list':demo.group==='fullbody-emotion'?'fullbody-emotion-list':demo.group==='limbs'?'limb-list':demo.group==='performance'?'performance-list':'demo-list').append(button);
  }
  $('prompt-form').onsubmit=async e=>{
    e.preventDefault();const text=$('prompt').value.trim();if(!text){toast('先描述一下你希望她怎样动。');return;}
    $('submit-prompt').disabled=true;
    try{const item=await api('/api/inbox',{prompt:text,backend});$('prompt-result').textContent=`#${item.id} · ${backend==='vts'?'VTS':'网页'} · 已进入指令箱，等待当前 Codex 理解与编排。`;$('prompt').value='';const d=await api('/api/inbox');renderInbox(d.requests);toast('已保存到本地指令箱。');}
    catch(error){$('prompt-result').textContent=error.message;}finally{$('submit-prompt').disabled=false;}
  };
  $('copy-handoff').onclick=async()=>{
    const text=`请读取鲸语 L2D 本地桥 ${location.origin}/api/inbox 中待处理的指令，按 /api/capabilities 的真实能力编排动作计划，通过 /api/execute 执行，并检查舞台完成回执。`;
    try{await navigator.clipboard.writeText(text);toast('接单指令已复制，粘贴给当前 Codex 即可。');}catch{toast('浏览器未允许复制；请直接告诉 Codex“处理 L2D 指令箱”。');}
  };
  $('copy-plan').onclick=async()=>{try{await navigator.clipboard.writeText($('compiled-json').textContent);toast('已复制动作计划。');}catch{toast('请手动选择并复制计划。');}};
  $('stop').onclick=async()=>{stopLocal();try{await api('/api/stop',{});}catch(e){toast(e.message);}};
  $('pause').onclick=()=>{if(!engine?.job)return;engine.paused=!engine.paused;$('pause').textContent=engine.paused?'▷':'Ⅱ';$('pause').setAttribute('aria-label',engine.paused?'继续动作':'暂停动作');setExecution(engine.paused?'动作已暂停':'舞台正在执行');};
  for(const b of document.querySelectorAll('[data-view]'))b.onclick=()=>{view=b.dataset.view;document.querySelectorAll('[data-view]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));resize();};
  $('idle-toggle').onchange=e=>{if(engine)engine.idle=e.target.checked;};
  $('physics-toggle').onchange=e=>{if(model)model.internalModel.physics=e.target.checked?physics:undefined;};
  $('strength').oninput=e=>{const v=Number(e.target.value);$('strength-value').textContent=`${Math.round(v*100)}%`;if(engine)engine.amplitude=v;};
  $('scene').onpointermove=e=>{if(!$('gaze-toggle').checked||!engine)return;const r=$('scene').getBoundingClientRect();engine.gaze={x:((e.clientX-r.left)/r.width-.5)*2,y:(.5-(e.clientY-r.top)/r.height)*2};};
  $('scene').onpointerleave=()=>{if(engine)engine.gaze=null;};$('gaze-toggle').onchange=e=>{if(!e.target.checked&&engine)engine.gaze=null;};
  $('open-research').onclick=()=>$('research-dialog').showModal();$('close-research').onclick=()=>$('research-dialog').close();
  $('research-dialog').onclick=e=>{if(e.target===$('research-dialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}};
}
// Spout2 is Windows-only, so the native frame stream is offered only where it exists.
function applyPlatform(state){
  if(state.nativeCapture===false){
    const option=$('export-renderer').querySelector('option[value="vts"]');
    if(option){option.disabled=true;option.textContent='VTS 原生画面 · Spout2（仅 Windows）';}
    $('export-renderer').value='web';
    $('export-source-note').textContent=`当前平台（${state.platform||'非 Windows'}）不支持 Spout2 原生采集；网页渲染导出可用。`;
    $('capture-check').disabled=true;
    const details=document.querySelector('.export-controls details');if(details)details.hidden=true;
  }
}
try{
  [profile,demos,state]=await Promise.all([api('/data/model-profile.json'),api('/api/demos'),api('/api/state')]);
  applyPlatform(state);
  bridgeOnline(true);renderInbox(state.inbox);mountControls();connectEvents(state.seq);
  if(state.activeJob&&['queued','playing'].includes(state.activeJob.status))pendingJob=state.activeJob;
  if(state.activeJob){
    lastJob=state.activeJob;
    renderPlan(state.activeJob);
    if(state.activeJob.status==='completed')setExecution('上次动作已完成 · 当前自然待机');
    else if(state.activeJob.status==='interrupted')setExecution('上次动作已停止');
    else if(state.activeJob.status==='error')setExecution('上次动作执行失败');
  }
  await loadModel();
  if(state.activeJob?.backend==='vts')backendJob(state.activeJob);
}catch(error){
  ready=false;$('loading').hidden=true;$('stage-error').hidden=false;$('stage-error').textContent=`模型加载失败：${error.message}`;$('model-state').textContent='加载失败';
  console.error(error);if(pendingJob)report('error',pendingJob,error.message);
}
