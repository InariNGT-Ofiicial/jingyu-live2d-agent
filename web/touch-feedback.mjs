import {bindHoldDrag} from './hold-drag.mjs';
import {TouchVoice} from './touch-voice.mjs';
// Model-relative hit zones; no game assets or game dialogue are reused.
export const TOUCH_ZONES=[
 {id:'chest',label:'胸口',x:.5,y:.35,rx:.13,ry:.065},
 {id:'thigh',label:'左侧大腿上部',x:.445,y:.64,rx:.055,ry:.055},
 {id:'thigh',label:'右侧大腿上部',x:.555,y:.64,rx:.055,ry:.055}
];
export function hitZone(x,y,special=true){
 if(x<.22||x>.78||y<.08||y>.98)return null;
 if(special)for(const z of TOUCH_ZONES)if(((x-z.x)/z.rx)**2+((y-z.y)/z.ry)**2<=1)return z.id;
 return 'normal';
}
export const REACTION_NAMES={normal:['抚胸点头','持草侧看','双手招呼','歪头眨眼'],chest:['后撤抚胸','侧闪抬指','摇头躲闪','害羞回望'],thigh:['侧身收势','侧闪抚胸','低头摇头','转头回望']};
export function reaction(zone,repeated=false,variant=0){
 variant=Math.max(0,Math.min(3,Math.floor(variant)));
 const text=zone!=='normal'?(repeated?'又被你逗笑啦。':'哎呀，你又在逗我啦。'):(repeated?'我在呢，有什么想说的？':'嗯？你在叫我吗？');
 const gesture=(paired=false)=>({kind:'gesture',name:'hand_on_chest',...(paired?{pair:'point'}:{}),at:.3,duration:4.4});
 const normalSets=[
  [gesture(),{kind:'nod',at:0,duration:1.7,strength:.65,count:2},{kind:'smile',at:0,duration:4.4,strength:.65}],
  [{kind:'gesture',name:'grass',at:.3,duration:4.4},{kind:'trajectory',at:0,duration:4.4,frames:[{time:.3,values:{AngleX:28,PositionX:22,PositionZ:12}},{time:.85,values:{AngleX:24,PositionX:18,PositionZ:9}},{time:1.4,values:{AngleX:-22,PositionX:-16,PositionZ:-8}},{time:2.1,values:{AngleX:-18,PositionX:-12,PositionZ:-6}},{time:3.8,values:{AngleX:6,PositionX:3,PositionZ:2}}]},{kind:'smile',at:0,duration:4.4,strength:.7}],
  [gesture(true),{kind:'nod',at:0,duration:1.8,strength:.85,count:2},{kind:'pose',at:0,duration:4.4,values:{LeanInput:-12,AngleZ:10}},{kind:'smile',at:0,duration:4.4,strength:.7}],
  [{kind:'tilt',direction:'left',at:0,duration:4,strength:.85},{kind:'blink',side:'left',at:1.8,duration:.65,count:1},{kind:'smile',at:0,duration:4.4,strength:.6}]
 ];
 let actions=normalSets[variant];
 if(zone==='chest'||zone==='thigh'){
  const side=(zone==='chest'?-1:1)*(variant%2?-1:1),boost=repeated?1.2:1.12;
  const frame=(time,lean,shift,roll,hx,hy,eye,open,brow)=>({time,values:{
   LeanInput:lean*boost,PositionX:side*shift*boost,PositionZ:side*roll,
   AngleX:side*hx,AngleY:hy,AngleZ:side*roll*.85,
   ParamEyeBallX:side*eye,ParamEyeBallY:hy<0?-.55:.2,
   ParamEyeLOpen:open,ParamEyeROpen:open,BrowInnerUp:brow,ParamMouthForm:time<.55?0:.3}});
  actions=[{kind:'trajectory',at:0,duration:5.2,frames:[
   frame(.22,zone==='chest'?22:14,zone==='chest'?12:22,12,12,5,.5,1.15,.7),
   frame(.55,20,22,17,28,-7,.8,.7,.5),
   frame(.95,16,19,14,25,-16,.8,.62,.38),
   frame(1.5,variant===2?20:15,variant===1?23:18,15,variant===2?-28:28,-16,variant===2?-.65:.65,.64,.35),
   frame(2.15,12,variant===3?-18:14,12,variant===3?-26:20,-10,variant===3?-.5:.35,.75,.25),
   frame(3.1,7,8,6,12,-7,.25,.8,.2),
   frame(4.4,3,3,2,5,-4,.1,.9,.1),
   frame(5.0,0,0,0,0,0,0,1,0)
  ]},{kind:'expression',name:'脸红',at:.2,duration:5.0,strength:.9}];
  const hand=(zone==='chest'?['hand_on_chest','point',null,null]:[null,'hand_on_chest','point',null])[variant];
  if(hand)actions.push({kind:'gesture',name:hand,at:.25,duration:4.6});
 }
 return {text,variant,voiceKey:(zone==='normal'?'normal-':'special-')+(repeated?'repeat':variant),name:REACTION_NAMES[zone][variant],displayMs:zone==='normal'?5500:5900,plan:{version:1,title:REACTION_NAMES[zone][variant],intent:'点击互动 · '+zone,summary:text,actions}};
}
export class TouchGate{
 constructor(random=Math.random){this.last=-Infinity;this.zone=null;this.pending=false;this.random=random;this.variants=new Map();this.remaining=new Map();this.lastHands=null;}
 accept(zone,now,busy){
  if(busy||this.pending||now-this.last<3500)return null;
  const repeated=this.zone===zone&&now-this.last<15000;this.last=now;this.zone=zone;const previous=this.variants.get(zone);
  let pool=this.remaining.get(zone);if(!pool?.length)pool=[0,1,2,3];
  const hands=v=>reaction(zone,repeated,v).plan.actions.filter(a=>a.kind==='gesture').map(a=>a.name+(a.pair?'+'+a.pair:'')).join(',')||'rest';
  let candidates=pool.filter(v=>v!==previous&&hands(v)!==this.lastHands);
  if(!candidates.length)candidates=pool.filter(v=>v!==previous);
  if(!candidates.length)candidates=pool;
  const variant=candidates[Math.floor(this.random()*candidates.length)];
  this.remaining.set(zone,pool.filter(v=>v!==variant));this.variants.set(zone,variant);this.lastHands=hands(variant);return reaction(zone,repeated,variant);
 }
}
export function bindTouchFeedback({stage,canvas,renderer,model,engine,busy,play,occluded=()=>false}){
 const q=id=>document.getElementById(id),gate=new TouchGate();let down=null;
 stage.getTouchGeometry=()=>{const r=canvas.getBoundingClientRect(),b=model.getBounds();return {x:r.left+b.x/renderer.screen.width*r.width,y:r.top+b.y/renderer.screen.height*r.height,width:b.width/renderer.screen.width*r.width,height:b.height/renderer.screen.height*r.height};};
 const settingsKey='jingyu-touch-v1';let settings={enabled:true,special:true};
 try{settings={...settings,...JSON.parse(localStorage.getItem(settingsKey)||'{}')};}catch{}
 q('touch-toggle').checked=!!settings.enabled;q('special-touch-toggle').checked=!!settings.special;
 for(const id of ['touch-toggle','special-touch-toggle'])q(id).onchange=()=>{try{localStorage.setItem(settingsKey,JSON.stringify({enabled:q('touch-toggle').checked,special:q('special-touch-toggle').checked}));}catch{}};
 const feedback=document.createElement('div');feedback.className='touch-feedback';feedback.setAttribute('role','status');stage.append(feedback);let timer;
 const say=(text,duration=3500)=>{feedback.textContent=text;clearTimeout(timer);timer=setTimeout(()=>{feedback.textContent='';},duration);};
 const voice=new TouchVoice({engine,onLine:say});voice.controls(q('touch-status'));
 model.internalModel.on('beforeModelUpdate',()=>voice.applyMouth(model.internalModel.coreModel));
 stage.getTouchVoiceState=()=>voice.status();
 stage.addEventListener('pointerdown',e=>{if(e.button===0&&!e.target.closest('button,input,select,a')){down={x:e.clientX,y:e.clientY,time:performance.now(),id:e.pointerId};if(q('touch-toggle').checked)voice.unlock().catch(()=>{});}});
 stage.addEventListener('pointercancel',()=>{down=null;});
 stage.addEventListener('pointerup',async e=>{
  const start=down;down=null;
  if(!start||e.pointerId!==start.id||!q('touch-toggle').checked||e.target.closest('button,input,select,a')||performance.now()-start.time>600||Math.hypot(e.clientX-start.x,e.clientY-start.y)>8||occluded(e))return;
  const r=canvas.getBoundingClientRect(),b=model.getBounds();
  const x=((e.clientX-r.left)/r.width*renderer.screen.width-b.x)/b.width,y=((e.clientY-r.top)/r.height*renderer.screen.height-b.y)/b.height;
  const zone=hitZone(x,y,q('special-touch-toggle').checked);if(!zone)return;
  if(busy()||voice.active){say('等这段表演结束，再来互动吧。');return;}
  const response=gate.accept(zone,performance.now(),false);if(!response)return;
  gate.pending=true;
  try{const clip=await voice.prepare(response.voiceKey);if(clip){response.text=clip.text;response.plan.summary=clip.text;}
   const job=await play(response.plan);say(response.text,response.displayMs);voice.play(response.voiceKey,job?.id).catch(()=>{});
   q('touch-status').textContent='最近互动：'+response.name+' · '+({normal:'普通点击',chest:'胸口 · 闪躲 / 害羞 / 回正',thigh:'大腿上侧 · 侧闪 / 害羞 / 回正'}[zone])+(clip?' · '+clip.emotion:'');}
  catch(e){say(e.message||'互动未执行');}finally{gate.pending=false;}
 });
 if(engine)bindHoldDrag({stage,engine,busy,geometry:stage.getTouchGeometry,occluded,enabled:()=>q('touch-toggle').checked,available:zone=>zone!=='chest'||(q('special-touch-toggle').checked&&!!model.internalModel.physics),onStart:zone=>voice.beginHold(zone),onEnd:()=>{voice.endHold();say('',0);}});
 return {bounds:()=>model.getBounds(),gate};
}
