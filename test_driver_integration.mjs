import assert from 'node:assert/strict';
import fs from 'node:fs';
import {MotionEngine} from './web/engine.mjs';
import {DriverPipeline,blendExpression} from './web/driver-pipeline.mjs';
const pipeline=new DriverPipeline(),order=[];
pipeline.add('expression',50,()=>order.push(50)).add('motion',30,()=>order.push(30));pipeline.run({});
assert.deepEqual(order,[30,50]);assert.throws(()=>pipeline.add('motion',1,()=>{}));
assert.equal(blendExpression(.4,.2,.5,'Add'),.5);
assert(Math.abs(blendExpression(.4,2,.5,'Multiply')-.6)<1e-8);
assert(Math.abs(blendExpression(.4,.8,.5,'Overwrite')-.6)<1e-8);
assert.throws(()=>blendExpression(.4,NaN,1,'Add'));
const profile=JSON.parse(fs.readFileSync(new URL('./web/data/model-profile.json',import.meta.url)));
for(const mode of ['Add','Multiply','Overwrite']){
 for(const reverse of [false,true]){
  const values=new Map(profile.allParameters.map(p=>[p.id,p.default]));
  const engine=new MotionEngine({setParameterValueById:(id,v)=>values.set(id,v),getParameterValueById:id=>values.get(id)},profile,()=>{});engine.idle=false;
  const base={id:'ParamMouthForm',action:0,start:0,duration:2,points:[[0,.4],[2,.4]]};
  const value=mode==='Multiply'?2:mode==='Overwrite'?.8:.2;
  const expression={id:'ParamMouthForm',action:1,start:0,duration:2,points:[[0,0],[2,0]],expression:{blend:mode,value,weightPoints:[[0,.5],[2,.5]],layer:'overlay'}};
  engine.start({id:'blend',compiled:{duration:3,steps:[{kind:'pose'},{kind:'expression'}],tracks:reverse?[expression,base]:[base,expression]}});
  for(let i=0;i<60;i++)engine.tick(1000/60);
  assert(Math.abs(values.get('ParamMouthForm')-(mode==='Add'?.5:.6))<1e-6);
  engine.stop();for(let i=0;i<60;i++)engine.tick(1000/60);assert(Math.abs(values.get('ParamMouthForm'))<1e-6);
  assert.throws(()=>engine.start({compiled:{tracks:[{id:'ParamAngleX'}]}}));
 }
}
console.log('Ordered phases, live-base blending, reversed track order, stop recovery and physics ownership passed.');
