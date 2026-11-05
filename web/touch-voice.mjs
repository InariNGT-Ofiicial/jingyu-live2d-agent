// Pre-rendered local DS voice: interaction never waits for model inference.
export class TouchVoice {
 constructor({engine,onLine=()=>{}}){
  this.engine=engine;this.onLine=onLine;this.active=false;this.serial=0;this.lastHold=-1;this.held=null;
  this.settings={enabled:true,volume:.7};this.buffers=new Map();this.bytes=new Map();
  try{Object.assign(this.settings,JSON.parse(localStorage.getItem('jingyu-touch-voice-v1')||'{}'));}catch{}
  this.settings.volume=Math.max(0,Math.min(1,Number(this.settings.volume)||0));
  this.ready=fetch('/assets/touch-voice/manifest.json').then(r=>{if(!r.ok)throw Error('触摸语音资源未就绪');return r.json();}).then(manifest=>{
   this.manifest=manifest;
   for(const clip of Object.values(manifest.clips))this.bytes.set(clip.id,fetch('/assets/touch-voice/'+clip.file).then(r=>{if(!r.ok)throw Error('语音资源缺失');return r.arrayBuffer();}).catch(()=>null));
   return manifest;
  }).catch(()=>null);
  window.addEventListener('pagehide',()=>this.endHold());
  document.addEventListener('visibilitychange',()=>{if(document.hidden)this.endHold();});
 }
 save(){localStorage.setItem('jingyu-touch-voice-v1',JSON.stringify(this.settings));}
 async unlock(){
  if(!this.settings.enabled)return;
  if(!this.ctx){
   this.ctx=new AudioContext();this.gain=this.ctx.createGain();this.gain.gain.value=this.settings.volume;
   this.analyser=this.ctx.createAnalyser();this.analyser.fftSize=256;this.levels=new Uint8Array(256);
   this.analyser.connect(this.gain);this.gain.connect(this.ctx.destination);
  }
  await this.ctx.resume();
 }
 async prepare(key){
  const manifest=await this.ready,clip=manifest?.clips[key];
  if(!clip)return null;
  if(this.ctx&&!this.buffers.has(key)){
   const bytes=await this.bytes.get(key);
   if(!bytes)return null;
   this.buffers.set(key,await this.ctx.decodeAudioData(bytes.slice(0)));
  }
  return clip;
 }
 async play(key,owner=null,hold=false){
  if(!this.settings.enabled)return null;
  this.stop();const serial=this.serial;
  await this.unlock();const clip=await this.prepare(key);
  if(serial!==this.serial||!clip||!this.settings.enabled||(hold&&!this.held))return null;
  this.gain.gain.cancelScheduledValues(this.ctx.currentTime);this.gain.gain.setValueAtTime(this.settings.volume,this.ctx.currentTime);
  const source=this.ctx.createBufferSource();source.buffer=this.buffers.get(key);source.connect(this.analyser);
  this.source=source;this.active=true;this.key=key;this.owner=owner;this.started=performance.now();
  source.onended=()=>{source.disconnect();if(this.source===source){this.source=null;this.active=false;}};
  source.start();this.onLine(clip.text,Math.max(1800,clip.duration*1000));return clip;
 }
 stop(fade=0){
  this.serial++;const source=this.source;this.source=null;this.active=false;this.owner=null;
  if(source){
   if(fade&&this.ctx){this.gain.gain.cancelScheduledValues(this.ctx.currentTime);this.gain.gain.setTargetAtTime(0,this.ctx.currentTime,.035);source.stop(this.ctx.currentTime+fade);}
   else{source.stop();source.disconnect();}
  }
 }
 beginHold(zone){
  this.endHold();this.held=zone;
  const epoch=this.holdEpoch;
  const next=async()=>{
   if(epoch!==this.holdEpoch||this.held!==zone||this.engine.job||document.hidden)return;
   const key=zone==='chest'?'hold-'+((++this.lastHold)%3):'normal-3';
   const clip=await this.play(key,null,true);
   if(epoch===this.holdEpoch&&this.held===zone&&zone==='chest')this.timer=setTimeout(()=>next().catch(()=>{}),(clip?.duration||2)*1000+4000);
  };
  next().catch(()=>{});
 }
 endHold(){this.holdEpoch=(this.holdEpoch||0)+1;clearTimeout(this.timer);this.held=null;this.stop(.12);}
 applyMouth(core){
  if(this.engine.speechReserved){this.endHold();return;}
  if(this.held&&(!this.engine.touchInput||this.engine.job))this.endHold();
  if(!this.active)return;
  if(this.engine.paused||(this.owner&&this.engine.job?.id!==this.owner&&performance.now()-this.started>500)){this.stop();return;}
  this.analyser.getByteTimeDomainData(this.levels);
  const rms=Math.sqrt(this.levels.reduce((sum,v)=>sum+((v-128)/128)**2,0)/this.levels.length);
  this.mouth=Math.min(1,rms*5);core.setParameterValueById('ParamMouthOpenY',this.mouth);
 }
 controls(host){
  const box=document.createElement('div');box.className='touch-voice-controls';
  const label=document.createElement('label'),toggle=document.createElement('input');toggle.type='checkbox';toggle.checked=this.settings.enabled;
  label.append(toggle,document.createTextNode('触摸情感语音'));
  const volume=document.createElement('label'),range=document.createElement('input');range.type='range';range.min=0;range.max=1;range.step=.05;range.value=this.settings.volume;
  volume.append(document.createTextNode('互动语音音量'),range);box.append(label,volume);host.before(box);
  toggle.onchange=()=>{this.settings.enabled=toggle.checked;if(!toggle.checked)this.stop(.12);try{this.save();}catch{}};
  range.oninput=()=>{this.settings.volume=Number(range.value);if(this.gain)this.gain.gain.setValueAtTime(this.settings.volume,this.ctx.currentTime);try{this.save();}catch{}};
 }
 status(){return {active:this.active,key:this.key,held:this.held,enabled:this.settings.enabled,volume:this.settings.volume,mouth:this.active?this.mouth||0:0};}
}
