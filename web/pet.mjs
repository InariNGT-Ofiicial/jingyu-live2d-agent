import {MotionEngine} from './engine.mjs';
const clientId='pet-'+crypto.randomUUID();
async function api(path,data){
 const r=await fetch(path,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{});
 if(!r.ok)throw Error(await r.text());return r.json();
}
try {
 const app=new PIXI.Application({view:document.querySelector('canvas'),resizeTo:window,resolution:Math.min(2,devicePixelRatio||1),autoDensity:true,backgroundAlpha:0,antialias:true});
 const [model,profile]=await Promise.all([PIXI.live2d.Live2DModel.from('/model/大肥鱼.model3.json',{autoInteract:false,motionPreload:'NONE'}),api('/data/model-profile.json')]);
 app.stage.addChild(model);model.anchor.set(.5,0);
 function resize(){model.scale.set(Math.min(innerWidth*.95/model.internalModel.originalWidth,innerHeight*.98/model.internalModel.originalHeight));model.position.set(innerWidth/2,innerHeight*.01);}
 resize();window.addEventListener('resize',resize);
 const engine=new MotionEngine(model.internalModel.coreModel,profile,(status,job)=>api('/api/report',{clientId,status,jobId:job.id,progress:status==='completed'?1:0}).catch(console.error));
 const m=model.internalModel;m.eyeBlink=undefined;m.breath=undefined;m.updateFocus=()=>{};
 let t=performance.now();m.updateNaturalMovements=()=>{const n=performance.now();engine.tick(n-t);t=n;};
 const state=await api('/api/state'),events=new EventSource('/api/events?after='+state.seq);
 events.addEventListener('execute',ev=>{const j=JSON.parse(ev.data);if(j.backend==='web')engine.start(j);});
 events.addEventListener('stop',()=>engine.stop());
 let lastBeat=performance.now(), lastFrame=engine.frames;
 const beat=()=>{
   const now=performance.now(), fps=Math.round((engine.frames-lastFrame)*1000/Math.max(1,now-lastBeat));
   lastFrame=engine.frames;lastBeat=now;
   return api('/api/heartbeat',{clientId,ready:true,telemetry:{...engine.telemetry(),presentation:'pet',exportReady:false,fps,framebuffer:[app.view.width,app.view.height]}}).catch(console.error);
 };
 await beat();setInterval(beat,2000);
}catch(e){document.querySelector('#error').textContent=e.message;}
