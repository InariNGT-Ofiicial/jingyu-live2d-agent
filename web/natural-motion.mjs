// Cursor input and persisted controls; explicit motion tracks retain priority in MotionEngine.
export function bindNaturalMotion(engine,stage,{disabled=false,externalPointer=false}={}){
 const get=id=>document.getElementById(id),key='jingyu-natural-motion-v1';
 let settings={gaze:true,sway:true,strength:.65,period:8,randomIdle:true,chestGain:1.3};
 try{const saved=JSON.parse(localStorage.getItem(key)||'null');if(saved)settings={...settings,...saved};}catch{}
 get('gaze-toggle').checked=settings.gaze===true;get('sway-toggle').checked=settings.sway===true;
 get('sway-strength').value=Number.isFinite(settings.strength)?Math.max(0,Math.min(1,settings.strength)):.65;
 get('sway-period').value=Number.isFinite(settings.period)?Math.max(4,Math.min(16,settings.period)):8;
 get('random-idle-toggle').checked=settings.randomIdle!==false;
 get('chest-gain').value=Number.isFinite(settings.chestGain)?Math.max(1,Math.min(1.8,settings.chestGain)):1.3;
 const apply=()=>{
  engine.randomIdle=!disabled&&get('random-idle-toggle').checked;engine.chestGain=disabled?1:Number(get('chest-gain').value);
  get('chest-value').textContent=engine.chestGain.toFixed(1)+'×';
  engine.sway=!disabled&&get('sway-toggle').checked;
  engine.swayStrength=Number(get('sway-strength').value);engine.swayPeriod=Number(get('sway-period').value);
  get('sway-value').textContent=Math.round(engine.swayStrength*100)+'%';get('sway-seconds').textContent=engine.swayPeriod+' 秒';
  if(!get('gaze-toggle').checked||disabled)engine.gaze=null;
  if(!disabled)try{localStorage.setItem(key,JSON.stringify({gaze:get('gaze-toggle').checked,sway:get('sway-toggle').checked,strength:engine.swayStrength,period:engine.swayPeriod,randomIdle:engine.randomIdle,chestGain:engine.chestGain}));}catch{}
 };
 for(const id of ['gaze-toggle','sway-toggle','sway-strength','sway-period','random-idle-toggle','chest-gain'])get(id).addEventListener('input',apply);
 window.addEventListener('pointermove',e=>{
  if(externalPointer||disabled||get('gaze-toggle').disabled||!get('gaze-toggle').checked)return;
  const r=stage.getBoundingClientRect();
  engine.gaze={x:Math.max(-1,Math.min(1,(e.clientX-r.left)/r.width*2-1)),y:Math.max(-1,Math.min(1,1-(e.clientY-r.top)/r.height*2))};
 });
 const reset=()=>{engine.gaze=null;};
 window.addEventListener('blur',()=>{if(!externalPointer)reset();});document.addEventListener('pointerout',e=>{if(!externalPointer&&!e.relatedTarget)reset();});
 document.addEventListener('visibilitychange',()=>{if(document.hidden)reset();});apply();
 return {reset};
}
