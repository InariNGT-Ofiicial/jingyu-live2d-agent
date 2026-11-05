import assert from 'node:assert/strict';
import {hitZone,reaction,TouchGate} from './web/touch-feedback.mjs';
assert.equal(hitZone(.5,.35),'chest');assert.equal(hitZone(.445,.64),'thigh');
assert.equal(hitZone(.5,.15),'normal');assert.equal(hitZone(.05,.35),null);
assert.equal(hitZone(.5,.35,false),'normal');
const g=new TouchGate();assert(g.accept('chest',0,false));assert.equal(g.accept('chest',1000,false),null);
assert.equal(g.accept('normal',4000,true),null);assert(g.accept('chest',4000,false).text.includes('逗笑'));
g.pending=true;assert.equal(g.accept('thigh',9000,false),null);
for(const zone of ['normal','chest','thigh'])assert(reaction(zone).plan.actions.length>0);
const variants=new TouchGate(()=>.5);let previous;
for(let t=0;t<80000;t+=4000){const r=variants.accept('chest',t,false);assert.notEqual(r.variant,previous);previous=r.variant;}
assert(reaction('normal',false,2).plan.actions.some(a=>a.pair==='point'));
console.log('Touch feedback: zones, opt-out, cooldown, busy/pending priority and repeat variants passed.');

for(const zone of ['normal','chest','thigh']){
 const gate=new TouchGate(()=>.5);
 for(let round=0;round<4;round++){
  const chosen=[];for(let i=0;i<4;i++)chosen.push(gate.accept(zone,(round*4+i)*6000,false).variant);
  assert.equal(new Set(chosen).size,4);
 }
}
const all=['normal','chest','thigh'].flatMap(z=>[0,1,2,3].map(v=>reaction(z,false,v)));
assert.equal(all.filter(r=>r.plan.actions.some(a=>a.pair)).length,1);
assert(all.some(r=>r.plan.actions.some(a=>a.name==='grass')));
assert(all.filter(r=>!r.plan.actions.some(a=>a.kind==='gesture')).length>=4);
