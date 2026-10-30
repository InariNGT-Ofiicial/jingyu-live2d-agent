// Reuse the actual web engine; bake its upstream inputs at a deterministic 60 Hz.
import fs from 'node:fs';
import {MotionEngine} from './web/engine.mjs';
const [compiledPath,outputPath]=process.argv.slice(2);
if(!compiledPath||!outputPath)throw Error('Usage: node export_vts_motion.mjs compiled.json output.motion3.json');
const compiled=JSON.parse(fs.readFileSync(compiledPath,'utf8'));
const profile=JSON.parse(fs.readFileSync(new URL('./web/data/model-profile.json',import.meta.url),'utf8'));
const values=new Map(profile.allParameters.map(p=>[p.id,p.default]));
const core={setParameterValueById:(id,v)=>values.set(id,v),getParameterValueById:id=>values.get(id)??0};
const engine=new MotionEngine(core,profile,()=>{});engine.start({id:'vts-bake',compiled});
const outputs=new Set(profile.physicsOutputIds),ids=[...engine.managed].filter(id=>!outputs.has(id)&&values.has(id)).sort();
const fps=60, duration=compiled.duration, count=Math.ceil(duration*fps),samples=[];
let prev=0;
for(let i=0;i<=count;i++){
  const t=Math.min(i/fps,duration);engine.tick((t-prev)*1000);prev=t;
  samples.push({time:t,values:Object.fromEntries(ids.map(id=>[id,values.get(id)]))});
}
const curves=ids.map(id=>({Target:'Parameter',Id:id,FadeInTime:0,FadeOutTime:0,Segments:samples.flatMap((s,i)=>i?[0,+s.time.toFixed(7),+s.values[id].toFixed(7)]:[0,+s.values[id].toFixed(7)])}));
const motion={Version:3,Meta:{Duration:duration,Fps:fps,Loop:false,AreBeziersRestricted:true,CurveCount:curves.length,TotalSegmentCount:curves.length*count,TotalPointCount:curves.length*(count+1),UserDataCount:0,TotalUserDataSize:0,FadeInTime:0,FadeOutTime:0},Curves:curves,UserData:[]};
fs.writeFileSync(outputPath,JSON.stringify(motion));
fs.writeFileSync(outputPath.replace('.motion3.json','-inputs.json'),JSON.stringify({fps,duration,ids,samples}));
console.log(JSON.stringify({duration,fps,curves:ids.length,frames:samples.length,excludedPhysicsOutputs:profile.physicsOutputIds.length}));
