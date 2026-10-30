import {DriverPipeline,blendExpression} from './driver-pipeline.mjs';
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const smooth=t=>t*t*(3-2*t);
export function samplePoints(points,t){
  if(t<=points[0][0])return points[0][1];
  for(let i=1;i<points.length;i++)if(t<=points[i][0]){
    const [a,x]=points[i-1],[b,y]=points[i];return x+(y-x)*smooth(clamp((t-a)/Math.max(1e-8,b-a),0,1));
  }
  return points.at(-1)[1];
}
function bez(a,b,c,d,t){return (1-t)**3*a+3*(1-t)**2*t*b+3*(1-t)*t*t*c+t**3*d;}
export function sampleMotion(s,t){
  let prev=[s[0],s[1]],i=2;
  while(i<s.length){
    const kind=s[i++];let end,c1,c2;
    if(kind===1){c1=s.slice(i,i+2);c2=s.slice(i+2,i+4);end=s.slice(i+4,i+6);i+=6;}
    else{end=s.slice(i,i+2);i+=2;}
    if(t<=end[0]){
      if(kind===0)return prev[1]+(end[1]-prev[1])*clamp((t-prev[0])/Math.max(1e-8,end[0]-prev[0]),0,1);
      if(kind===2)return prev[1];if(kind===3)return end[1];
      let lo=0,hi=1;for(let k=0;k<15;k++){const u=(lo+hi)/2;if(bez(prev[0],c1[0],c2[0],end[0],u)<t)lo=u;else hi=u;}
      return bez(prev[1],c1[1],c2[1],end[1],(lo+hi)/2);
    }prev=end;
  }return prev[1];
}
export class MotionEngine{
  constructor(core,profile,notify){
    this.core=core;this.profile=profile;this.notify=notify;this.params=new Map(profile.allParameters.map(p=>[p.id,p]));
    this.managed=new Set([...profile.parameters.map(p=>p.id),...Array.from({length:13},(_,i)=>`key${i+1}`),...profile.idleMotion.Curves.filter(c=>c.Target==='Parameter').map(c=>c.Id)]);
    this.current=new Map();this.clock=0;this.elapsed=0;this.job=null;this.paused=false;this.idle=true;this.amplitude=1;this.gaze=null;this.frames=0;this.lastStatus='idle';
    this.physicsOutputs=new Set(profile.physicsOutputIds||[]);
    this.pipeline=new DriverPipeline()
      .add('idle',10,c=>this.applyIdle(c)).add('gaze',20,c=>this.applyGaze(c))
      .add('motion',30,c=>this.applyMotion(c)).add('blink',40,c=>this.applyBlink(c))
      .add('expression',50,c=>this.applyExpressions(c)).add('commit',60,c=>this.commit(c));
  }
  start(job){
    for(const track of job.compiled.tracks){
      if(!this.params.has(track.id)||this.physicsOutputs.has(track.id))throw new Error(`unwritable driver parameter: ${track.id}`);
    }
    for(const track of job.compiled.tracks)this.managed.add(track.id);
    this.job=job;this.elapsed=0;this.paused=false;this.lastStatus='playing';this.notify('playing',job);
  }
  stop(){this.job=null;this.elapsed=0;this.paused=false;this.lastStatus='idle';}
  tick(deltaMs){
    const wallDt=Math.max(0,deltaMs/1000),dt=Math.min(wallDt,1);this.clock+=wallDt;this.frames++;
    if(this.job&&!this.paused)this.elapsed+=wallDt;
    const target=new Map([...this.managed].map(id=>[id,this.params.get(id)?.default??0]));
    const context={target,set:(id,v)=>target.set(id,v),phase:this.clock,dt,explicit:new Set(),expressions:[]};
    this.pipeline.run(context);
    if(this.job&&this.elapsed>=this.job.compiled.duration){
      const ended=this.job;this.job=null;this.lastStatus='completed';this.notify('completed',ended);
    }
  }
  applyIdle({set,phase}){
    if(this.idle){
      set('ParamBreath',.42+.24*Math.sin(phase*1.45));
      set('AngleX',1.15*Math.sin(phase*.55));set('AngleY',.7*Math.sin(phase*.72+.4));set('AngleZ',.6*Math.sin(phase*.48));
      set('PositionX',.5*Math.sin(phase*.55-.2));set('PositionZ',.35*Math.sin(phase*.48-.25));
      const motion=this.profile.idleMotion,t=phase%motion.Meta.Duration;
      for(const c of motion.Curves)if(c.Target==='Parameter')set(c.Id,sampleMotion(c.Segments,t));
    }
  }
  applyGaze({set}){
    if(this.gaze){set('ParamEyeBallX',this.gaze.x*.5);set('ParamEyeBallY',this.gaze.y*.4);}
  }
  applyMotion({set,explicit,expressions}){
    if(this.job){
      for(const tr of this.job.compiled.tracks){
        const local=this.elapsed-tr.start;
        if(local<0||local>tr.duration)continue;
        if(tr.expression){expressions.push({track:tr,local});explicit.add(tr.id);continue;}
        const p=this.params.get(tr.id),kind=this.job.compiled.steps[tr.action]?.kind;
        let v=samplePoints(tr.points,local);
        if(kind!=='gesture'&&kind!=='expression'&&kind!=='blink')v=p.default+(v-p.default)*this.amplitude;
        set(tr.id,v);explicit.add(tr.id);
      }
    }
  }
  applyBlink({set,explicit,phase}){
    if(this.idle){
      const b=phase%4.7;let open=1;
      if(b>3.8&&b<4.12)open=b<3.91?1-smooth((b-3.8)/.11):smooth(clamp((b-3.96)/.16,0,1));
      for(const id of ['ParamEyeLOpen','ParamEyeROpen'])if(!explicit.has(id))set(id,open);
    }
  }
  applyExpressions({target,set,expressions}){
    this.expressionTelemetry=[];
    for(const {track,local} of expressions){
      const e=track.expression,w=samplePoints(e.weightPoints,local),p=this.params.get(track.id);
      const base=target.get(track.id)??p.default;
      set(track.id,blendExpression(base,e.value,w,e.blend));
      this.expressionTelemetry.push({id:track.id,blend:e.blend,layer:e.layer,weight:+w.toFixed(3),base:+base.toFixed(4)});
    }
  }
  commit({target,dt}){
    for(const [id,v]of target){
      const p=this.params.get(id);if(!p)continue;
      const prev=this.current.get(id)??p.default,tau=id.includes('Eye')&&id.includes('Open')?.016:.055;
      const value=clamp(prev+(v-prev)*(1-Math.exp(-dt/tau)),p.min,p.max);
      this.current.set(id,value);this.core.setParameterValueById(id,value);
    }
  }
  telemetry(){
    const ids=['AngleX','AngleY','AngleZ','ParamAngleX','ParamAngleY','ParamAngleZ','ParamEyeLOpen','ParamEyeROpen','ParamMouthForm','ParamMouthOpenY','ParamBreath','Movement1','Movement2','Movement3','PositionX','PositionY','PositionZ','HipAngleX','LEGAngleZ2','Param33','LArm','LForearm','LWrist','LHand','LHand2','RArm','RForearm','RWrist','RHand','RHand2','Param36','Param39','Param41','Param42','Param43','Param62','Param59','Param60','Param61'];
    const observed=[...new Set([...ids,...this.profile.parameters.map(p=>p.id),...this.managed])];
    return {elapsed:+this.elapsed.toFixed(3),frames:this.frames,jobId:this.job?.id??null,status:this.lastStatus,amplitude:this.amplitude,
      driverStages:this.pipeline.names(),expressions:this.expressionTelemetry||[],
      nonFinite:this.profile.allParameters.filter(p=>!Number.isFinite(this.core.getParameterValueById(p.id))).map(p=>p.id),
      values:Object.fromEntries(observed.map(id=>[id,+this.core.getParameterValueById(id).toFixed(4)]))};
  }
}
