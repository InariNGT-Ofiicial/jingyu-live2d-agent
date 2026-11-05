import assert from 'node:assert/strict';
import {IdleEvents,attachChestPhysics} from './web/idle-events.mjs';
let seed=31;const rng=()=>((seed=(seed*1664525+1013904223)>>>0)/4294967296);
const events=new IdleEvents(rng),names=[];let lastCount=0,peak=0;
for(let t=0;t<240;t+=.05){
 const values=events.sample(t,true,.7);
 assert(Object.values(values).every(Number.isFinite));peak=Math.max(peak,...Object.values(values).map(Math.abs));
 if(events.count!==lastCount){names.push(events.active.name);lastCount=events.count;assert(Object.values(values).every(v=>v===0));}
}
assert(new Set(names).size===6);assert(names.every((n,i)=>i===0||n!==names[i-1]));assert(peak>1&&peak<=3.5);
assert.deepEqual(events.sample(241,false),{});assert.equal(events.active,null);
const values={ChestY1:0,Other:0},core={getParameterValueById:id=>values[id],setParameterValueById:(id,v)=>values[id]=v};
const internal={coreModel:core,physics:{evaluate(){values.ChestY1=.8;values.Other=.2;}}};let gain=1.8;
attachChestPhysics(internal,{allParameters:[{id:'ChestY1',default:0,min:-1,max:1}]},()=>gain);
internal.physics.evaluate();assert.equal(values.ChestY1,1);assert.equal(values.Other,.2);
gain=1;internal.physics.evaluate();assert.equal(values.ChestY1,.8);
console.log('Idle events: six variants, no repeat, zero-edge envelopes, suppression, chest gain/clamp/reset passed.');
