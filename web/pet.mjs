import {MotionEngine} from './engine.mjs';
import {bindNaturalMotion} from './natural-motion.mjs';
import {attachChestPhysics} from './idle-events.mjs';
import {bindTouchFeedback} from './touch-feedback.mjs';
import {installStockingShader,bindOriginalStockings} from './original-stockings.mjs';
import {bindDesktopGaze} from './desktop-gaze.mjs';
const clientId='pet-'+crypto.randomUUID(),native=window.jingyuPet;
async function api(path,data){
 const r=await fetch(path,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{});
 if(!r.ok)throw Error(await r.text());return r.json();
}
try{
 const stage=document.querySelector('#pet-stage'),canvas=document.querySelector('canvas');
 if(native){
  document.querySelector('#pet-tools').hidden=false;
  for(const button of document.querySelectorAll('[data-control]'))button.onclick=()=>native.control(button.dataset.control);
  window.addEventListener('keydown',e=>{if(e.key==='Escape')native.control('close');});
  let lastZoom=0;stage.addEventListener('wheel',e=>{e.preventDefault();if(performance.now()-lastZoom>120){native.control(e.deltaY<0?'larger':'smaller');lastZoom=performance.now();}},{passive:false});
 }
 const app=new PIXI.Application({view:canvas,resizeTo:stage,resolution:Math.min(2,devicePixelRatio||1),autoDensity:true,backgroundAlpha:0,antialias:true,powerPreference:'high-performance'});
 app.ticker.maxFPS=60;
 const setStockingShader=installStockingShader(app.renderer.gl);
 const [model,profile]=await Promise.all([PIXI.live2d.Live2DModel.from('/model/大肥鱼.model3.json',{autoInteract:false,autoUpdate:true,motionPreload:'NONE'}),api('/data/model-profile.json')]);
 app.stage.addChild(model);model.anchor.set(.5,0);
 function resize(){
  const w=stage.clientWidth,h=stage.clientHeight;app.renderer.resize(w,h);
  model.scale.set(Math.min(w*.94/model.internalModel.originalWidth,h*.94/model.internalModel.originalHeight));model.position.set(w/2,h*.04);
 }
 resize();new ResizeObserver(resize).observe(stage);
 let active=false,backend='web',pending=false;
 const report=(status,job)=>{if(status==='completed')active=false;api('/api/report',{clientId,status,jobId:job.id,progress:status==='completed'?1:0}).catch(console.error);};
 const engine=new MotionEngine(model.internalModel.coreModel,profile,report);
 bindNaturalMotion(engine,stage,{externalPointer:!!native});
 bindOriginalStockings({model,stage,canvas,renderer:app.renderer,setShaderProgress:setStockingShader,busy:()=>active||pending||backend!=='web'});
 attachChestPhysics(model.internalModel,profile,()=>engine.chestGain,()=>engine.job?null:engine.touchInput);
 bindTouchFeedback({stage,canvas,renderer:app.renderer,model,engine,busy:()=>active||pending||backend!=='web',play:async plan=>{
  pending=true;try{return await api('/api/execute',{plan,backend:'web'});}finally{pending=false;}
 }});
 if(native){
  document.querySelector('#gaze-label').textContent='注视整个桌面的鼠标';
  const unbind=bindDesktopGaze({native,engine,geometry:stage.getTouchGeometry,enabled:()=>document.querySelector('#gaze-toggle').checked});
  window.addEventListener('beforeunload',unbind);
 }
 const settings=document.querySelector('#pet-settings');
 document.querySelector('#pet-settings-button').onclick=()=>{settings.hidden=!settings.hidden;document.querySelector('#pet-settings-button').setAttribute('aria-expanded',String(!settings.hidden));};
 document.querySelector('#close-pet-settings').onclick=()=>{settings.hidden=true;document.querySelector('#pet-settings-button').setAttribute('aria-expanded','false');};
 const m=model.internalModel;m.eyeBlink=undefined;m.breath=undefined;m.updateFocus=()=>{};
 let renderedTelemetry=null;
 // Cubism restores cached parameters after drawing; sample the values actually rendered.
 m.on('beforeModelUpdate',()=>{renderedTelemetry=engine.telemetry();});
 let tickAt=performance.now();m.updateNaturalMovements=()=>{const now=performance.now();engine.tick(now-tickAt);tickAt=now;};
 const state=await api('/api/state');backend=state.backend||'web';
 const events=new EventSource('/api/events?after='+state.seq);
 if(state.activeJob?.backend==='web'&&['queued','playing'].includes(state.activeJob.status)){
  const elapsed=Math.max(0,(Date.now()-Date.parse(state.activeJob.createdAt))/1000);
  if(elapsed<state.activeJob.compiled.duration){active=true;engine.start(state.activeJob);engine.elapsed=elapsed;}
 }
 events.addEventListener('execute',ev=>{const job=JSON.parse(ev.data);if(job.backend==='web'){active=true;engine.start(job);}});
 events.addEventListener('stop',()=>{active=false;engine.stop();});
 events.addEventListener('backend',ev=>{backend=JSON.parse(ev.data).backend;});
 events.addEventListener('pause',()=>{engine.paused=true;});
 events.addEventListener('resume',()=>{engine.paused=false;});
 let lastBeat=performance.now(),lastFrame=engine.frames,fps=0;
 const snapshot=()=>({...renderedTelemetry||engine.telemetry(),presentation:'pet',renderer:'web',exportReady:false,fps,gaze:engine.gaze,gazeSource:native?'desktop':'window',
  framebuffer:[app.view.width,app.view.height],devicePixelRatio:app.renderer.resolution,transparent:true});
 window.jingyuPetState=()=>({ready:true,...snapshot()});
 const beat=()=>{
  const now=performance.now();fps=Math.round((engine.frames-lastFrame)*1000/Math.max(1,now-lastBeat));
  lastFrame=engine.frames;lastBeat=now;
  const telemetry=snapshot();native?.telemetry(telemetry);
  return api('/api/heartbeat',{clientId,ready:true,telemetry}).then(()=>{document.querySelector('#error').textContent='';}).catch(error=>{document.querySelector('#error').textContent='工作台连接已断开：'+error.message;});
 };
 // The model must render before the native controller reports a successful start.
 app.renderer.render(app.stage);stage.dataset.ready='true';await beat();native?.ready();
 const timer=setInterval(beat,2000);
 window.addEventListener('beforeunload',()=>{clearInterval(timer);events.close();});
}catch(error){document.querySelector('#error').textContent=error.message;native?.error(error.message);}
