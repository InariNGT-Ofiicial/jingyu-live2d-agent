// Pointer gestures only; the model keeps its authored physics and texture assets.
export function dragValues(zone,dx,dy){
 const limit=v=>Math.max(-1,Math.min(1,v));
 return {zone,x:limit(dx/.12),y:limit(-dy/.1)};
}
export function bindHoldDrag({stage,engine,busy,enabled,geometry,occluded=()=>false,available=()=>true,onStart=()=>{},onEnd=()=>{}}){
 let press=null,timer=null;
 const status=()=>document.getElementById('touch-status');
 const release=()=>{
  clearTimeout(timer);const old=press;press=null;engine.touchInput=null;
  if(old?.active)onEnd(old.zone);
  if(old?.active&&stage.hasPointerCapture?.(old.id))stage.releasePointerCapture(old.id);
  delete stage.dataset.holding;
 };
 const point=e=>{const g=geometry();return {x:(e.clientX-g.x)/g.width,y:(e.clientY-g.y)/g.height};};
 stage.addEventListener('pointerdown',e=>{
  if(e.button!==0||!enabled()||busy()||occluded(e)||e.target.closest('button,input,select,a'))return;
  const p=point(e),zone=((p.x-.5)/.13)**2+((p.y-.35)/.065)**2<=1?'chest':p.x>.33&&p.x<.67&&p.y>.07&&p.y<.25?'head':null;
  if(!zone||!available(zone))return;
  press={id:e.pointerId,p,last:p,zone,active:false};
  timer=setTimeout(()=>{
   if(!press||busy()||!enabled()){release();return;}
   press.active=true;stage.setPointerCapture(e.pointerId);stage.dataset.holding=zone;
   engine.touchInput=dragValues(zone,press.last.x-p.x,press.last.y-p.y);
   onStart(zone);
   if(status())status().textContent='长按拖动：'+(zone==='head'?'头部':'胸部')+' · 松手回弹';
  },450);
 });
 stage.addEventListener('pointermove',e=>{
  if(!press||e.pointerId!==press.id)return;
  if(busy()||!enabled()||occluded(e)){release();return;}
  press.last=point(e);
  if(press.active){e.preventDefault();engine.touchInput=dragValues(press.zone,press.last.x-press.p.x,press.last.y-press.p.y);}
 });
 // Capture runs before the short-click handler and prevents a release click.
 stage.addEventListener('pointerup',e=>{
  if(!press||e.pointerId!==press.id)return;
  if(press.active){e.stopImmediatePropagation();e.preventDefault();}
  release();
 },true);
 for(const name of ['pointercancel','lostpointercapture'])stage.addEventListener(name,release);
 for(const id of ['touch-toggle','special-touch-toggle','physics-toggle'])document.getElementById(id)?.addEventListener('change',release);
 window.addEventListener('blur',release);
 document.addEventListener('visibilitychange',()=>{if(document.hidden)release();});
 stage.getHoldState=()=>({active:!!press?.active,input:engine.touchInput,shyStrength:engine.touchShy||0});
 return release;
}
