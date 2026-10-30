import {sampleMotion} from './engine.mjs';
const nextTurn=()=>new Promise(resolve=>setTimeout(resolve,0));
const percentile=(xs,p)=>{const s=[...xs].sort((a,b)=>a-b);return s[Math.min(s.length-1,Math.floor(s.length*p))]||0;};

export class StressRunner{
  constructor({model,pixi,engine,profile,clientId,api,onStatus,onRestore}){Object.assign(this,{model,pixi,engine,profile,clientId,api,onStatus,onRestore});this.running=false;this.cancelled=false;}
  cancel(){this.cancelled=true;}
  async run(job){
    if(this.running||job.clientId!==this.clientId)return;
    this.running=true;this.cancelled=false;
    const {model,pixi,engine,api}=this,core=model.internalModel.coreModel,raw=core.getModel(),physics=model.internalModel.physics;
    const oldAuto=model.autoUpdate,oldScale=model.scale.x,oldResolution=pixi.renderer.resolution;
    const oldParts=Float32Array.from(raw.parts.opacities),defaults=Float32Array.from(raw.parameters.defaultValues);
    const gl=pixi.renderer.gl,started=performance.now(),rounds=job.rounds;
    const result={rounds,errors:[],warnings:[],parameterCoverage:{},parts:[],expressions:[],motions:[],vtsMappings:[],physics:[],renderVariants:[],recovery:{},summary:{}};
    let frames=0,lastYield=performance.now(),lastReport=0,currentPhase='',currentProgress=0;
    const timings=[];
    const fail=(message,detail)=>{if(result.errors.length<100)result.errors.push({phase:currentPhase,message,detail});};
    const reset=()=>{raw.parameters.values.set(defaults);raw.parts.opacities.set(oldParts);};
    const signature=()=>Array.from(raw.drawables.ids,(_,i)=>{
      if(!Live2DCubismCore.Utils.hasIsVisibleBit(raw.drawables.dynamicFlags[i]))return 0;
      const a=raw.drawables.vertexPositions[i];let sum=raw.drawables.opacities[i]*31;
      for(let j=0;j<a.length;j++)sum+=a[j]*(j%13+1);
      for(let k=0;k<4;k++)sum+=raw.drawables.multiplyColors[i*4+k]*(k+3)+raw.drawables.screenColors[i*4+k]*(k+7);
      return sum;
    });
    const frame=(label,fullAudit=false)=>{
      const t=performance.now();core.update();model.deltaTime=0;pixi.renderer.render(pixi.stage);frames++;
      if(gl.isContextLost())throw new Error('WebGL context lost');
      const error=gl.getError();if(error!==gl.NO_ERROR)fail('WebGL error',{label,error});
      for(let i=0;i<raw.parameters.count;i++)if(!Number.isFinite(raw.parameters.values[i])){fail('non-finite parameter',{label,id:raw.parameters.ids[i]});break;}
      for(let i=0;i<raw.drawables.count;i++){
        if(!Number.isFinite(raw.drawables.opacities[i]))fail('non-finite opacity',{label,id:raw.drawables.ids[i]});
        if(fullAudit)for(const v of raw.drawables.vertexPositions[i])if(!Number.isFinite(v)){fail('non-finite vertex',{label,id:raw.drawables.ids[i]});break;}
      }
      timings.push(performance.now()-t);
    };
    const progress=async(phase,ratio,force=false)=>{
      currentPhase=phase;currentProgress=ratio;this.onStatus(phase,ratio);
      if(this.cancelled)throw new Error('CANCELLED');
      const now=performance.now();
      if(force||now-lastReport>1200){lastReport=now;await api('/api/lab/report',{id:job.id,clientId:this.clientId,status:'running',progress:ratio,phase});await api('/api/heartbeat',{clientId:this.clientId,ready:true,telemetry:{diagnosticId:job.id,phase,frames}});}
      if(now-lastYield>70){lastYield=now;await nextTurn();}
    };
    try{
      const catalog=await api('/data/stress-catalog.json');
      engine.stop();pixi.stop();model.autoUpdate=false;model.deltaTime=0;
      // Only this isolated laboratory writes physical outputs directly. Normal plans remain restricted.
      reset();frame('baseline',true);const baseSig=signature();
      result.environment={coreVersion:Live2DCubismCore.Version.csmGetVersion(),gpuMaxTextureSize:gl.getParameter(gl.MAX_TEXTURE_SIZE),resolution:oldResolution,canvas:[gl.drawingBufferWidth,gl.drawingBufferHeight],textures:model.textures.map(t=>({valid:t.valid,width:t.width,height:t.height})),physicsLoaded:!!physics,rigCount:physics?._physicsRig?.subRigCount||0};
      for(let round=0;round<rounds;round++){
        for(let i=0;i<catalog.parameters.length;i++){
          const p=catalog.parameters[i];
          const row=result.parameterCoverage[p.id]??={id:p.id,name:p.name||p.id,tags:p.tags,rounds:0,targets:[],clampChecks:0};
          for(const v of [p.min,(p.min+p.max)/2,p.max]){
            reset();core.setParameterValueById(p.id,v);frame(p.id,round===0&&i%20===0);
            const actual=core.getParameterValueById(p.id);
            if(Math.abs(actual-v)>1e-4)fail('parameter value mismatch',{id:p.id,expected:v,actual});
            if(round===0)row.targets.push({requested:v,actual});
          }
          for(const [v,expected]of [[p.min-10,p.min],[p.max+10,p.max]]){
            core.setParameterValueById(p.id,v);const actual=core.getParameterValueById(p.id);row.clampChecks++;
            if(Math.abs(actual-expected)>1e-4)fail('clamp failed',{id:p.id,expected,actual});
          }
          row.rounds++;await progress(`全参数 ${round+1}/${rounds} · ${i+1}/509 · ${p.name||p.id}`,((round*509+i+1)/(rounds*509))*.46);
        }
      }
      reset();frame('parameter-recovery',true);
      result.recovery.afterParameters=signature().filter((v,i)=>Math.abs(v-baseSig[i])>1e-4).length;
      for(let i=0;i<raw.parts.count;i++){
        for(const opacity of [0,.5,1]){reset();raw.parts.opacities[i]=opacity;frame(`part:${i}`);}
        result.parts.push(raw.parts.ids[i]);await progress(`部件透明度 · ${i+1}/${raw.parts.count}`,.46+.05*(i+1)/raw.parts.count);
      }
      reset();frame('parts-recovery',true);
      result.recovery.afterParts=signature().filter((v,i)=>Math.abs(v-baseSig[i])>1e-4).length;
      let ei=0;
      for(const [name,expression]of Object.entries(catalog.expressions)){
        for(const weight of [.25,.6,1]){
          reset();for(const p of expression.Parameters){const d=core.getParameterValueById(p.Id);const v=p.Blend==='Multiply'?d*(1+(p.Value-1)*weight):p.Blend==='Overwrite'?d+(p.Value-d)*weight:d+p.Value*weight;core.setParameterValueById(p.Id,v);}
          frame(`expression:${name}:${weight}`,true);
        }
        result.expressions.push({name,parameters:expression.Parameters.map(x=>x.Id),weights:[.25,.6,1]});
        await progress(`原生表情 · ${++ei}/23 · ${name}`,.51+.04*ei/23);
      }
      let mi=0;
      for(const [name,motion]of Object.entries(catalog.motions)){
        reset();physics?.initialize();const curves=motion.Curves.filter(c=>c.Target==='Parameter');
        const n=Math.max(30,Math.ceil(motion.Meta.Duration*30));
        for(let f=0;f<=n;f++){
          const t=motion.Meta.Duration*f/n;
          for(const c of curves)core.setParameterValueById(c.Id,sampleMotion(c.Segments,t));
          physics?.evaluate(core,1/30);frame(`motion:${name}:${f}`,f===n);
          await progress(`原生动作 · ${mi+1}/8 · ${name}`,.55+.1*(mi+f/n)/8);
        }
        result.motions.push({name,frames:n+1,duration:motion.Meta.Duration,curves:curves.length,loop:motion.Meta.Loop});mi++;
      }
      for(let i=0;i<catalog.vtsMappings.length;i++){
        const m=catalog.vtsMappings[i];
        for(const u of [0,.5,1]){reset();core.setParameterValueById(m.OutputLive2D,m.OutputRangeLower+(m.OutputRangeUpper-m.OutputRangeLower)*u);frame(`VTS-map:${i}`);}
        result.vtsMappings.push({name:m.Name,input:m.Input,output:m.OutputLive2D,range:[m.OutputRangeLower,m.OutputRangeUpper],tested:'output-range-adapter',smoothingNotEmulated:m.Smoothing});
        await progress(`VTS 映射输出 · ${i+1}/40`,.65+.03*(i+1)/40);
      }
      if(!physics)throw new Error('Author physics missing');
      const paramMap=new Map(catalog.parameters.map(p=>[p.id,p]));
      for(const fps of [30,60,120]){
        reset();physics.initialize();const bounds=new Map(catalog.physicsOutputs.map(id=>[id,[Infinity,-Infinity]]));
        const framesPerRate=fps*4;
        for(let f=0;f<framesPerRate;f++){
          const t=f/fps;
          for(let i=0;i<catalog.externalPhysicsInputs.length;i++){
            const id=catalog.externalPhysicsInputs[i],p=paramMap.get(id);
            core.setParameterValueById(id,p.min+(p.max-p.min)*(.5+.48*Math.sin(t*(1.7+i%7*.25)+i*.8)));
          }
          // Native solver traverses all 131 rigs; downstream outputs are never overwritten here.
          physics.evaluate(core,1/fps);
          for(const [id,b]of bounds){const v=core.getParameterValueById(id);b[0]=Math.min(b[0],v);b[1]=Math.max(b[1],v);}
          frame(`physics:${fps}:${f}`,f%fps===0);
          await progress(`物理联动 · ${fps} Hz · ${f+1}/${framesPerRate}`,.68+.24*([30,60,120].indexOf(fps)+f/framesPerRate)/3);
        }
        result.physics.push({fps,frames:framesPerRate,rigs:catalog.physics.PhysicsSettings.map(r=>({id:r.Id,outputs:r.Output.map(o=>{const id=o.Destination.Id,b=bounds.get(id);return {id,min:b[0],max:b[1],span:b[1]-b[0]};})}))});
      }
      // Clothes2 is a switch: the broad sinusoidal probe can remain saturated.
      // Probe exact endpoints with settling, preserving the author's zero-weight rigs.
      result.targetedPhysics=[];reset();physics.initialize();
      for(const value of [0,1,0]){
        let min=Infinity,max=-Infinity;
        for(let f=0;f<180;f++){
          core.setParameterValueById('Clothes2',value);physics.evaluate(core,1/60);
          const v=core.getParameterValueById('Param34');min=Math.min(min,v);max=Math.max(max,v);
          frame(`switch:Clothes2:${value}:${f}`,f%60===0);
          await progress(`大小变切换 · Clothes2=${value} · ${f+1}/180`,.92);
        }
        result.targetedPhysics.push({input:'Clothes2',value,output:'Param34',min,max,settled:core.getParameterValueById('Param34')});
      }
      result.disabledPhysicsOutputs=catalog.physics.PhysicsSettings.flatMap(r=>r.Output.filter(o=>o.Weight===0).map(o=>({rig:r.Id,id:o.Destination.Id,weight:0})));
      reset();physics.initialize();
      for(const scale of [.8,1,1.6])for(const resolution of [1,1.5]){
        model.scale.set(oldScale*scale);pixi.renderer.resolution=resolution;pixi.renderer.resize(pixi.renderer.screen.width,pixi.renderer.screen.height);
        frame('render-variant',true);gl.finish();
        result.renderVariants.push({scale,resolution,width:gl.drawingBufferWidth,height:gl.drawingBufferHeight,webglError:gl.getError()});
        await progress(`渲染比例与像素密度 · ${result.renderVariants.length}/6`,.92+.06*result.renderVariants.length/6);
      }
      reset();model.scale.set(oldScale);pixi.renderer.resolution=oldResolution;pixi.renderer.resize(pixi.renderer.screen.width,pixi.renderer.screen.height);frame('final-neutral',true);
      result.recovery.final=signature().filter((v,i)=>Math.abs(v-baseSig[i])>1e-4).length;
      if(Object.values(result.recovery).some(x=>x))result.warnings.push('Some drawable signatures differ after neutral reset; inspect recovery counts and compare to independent Core tests.');
      result.summary={parameters:Object.keys(result.parameterCoverage).length,parts:result.parts.length,expressions:result.expressions.length,motions:result.motions.length,mappings:result.vtsMappings.length,physicsRigs:131,frames,seconds:(performance.now()-started)/1000,errors:result.errors.length,warnings:result.warnings.length,frameCpuMs:{p50:percentile(timings,.5),p95:percentile(timings,.95),p99:percentile(timings,.99),max:Math.max(...timings)}};
      await api('/api/lab/report',{id:job.id,clientId:this.clientId,status:result.errors.length?'failed':'completed',progress:1,phase:'测试完成，已恢复模型',result});
      this.onStatus(`压力测试完成 · ${frames} 帧 · ${result.errors.length} 项错误`,1);
    }catch(error){
      const status=error.message==='CANCELLED'?'cancelled':'failed';
      if(status==='failed')fail(error.message,error.stack);
      result.summary={frames,seconds:(performance.now()-started)/1000,errors:result.errors.length};
      try{await api('/api/lab/report',{id:job.id,clientId:this.clientId,status,progress:currentProgress,phase:status==='cancelled'?'已停止测试':'测试失败',result});}catch{}
      this.onStatus(status==='cancelled'?'压力测试已停止':`压力测试失败：${error.message}`,currentProgress);
    }finally{
      reset();physics?.initialize();core.saveParameters();core.update();model.scale.set(oldScale);pixi.renderer.resolution=oldResolution;pixi.renderer.resize(pixi.renderer.screen.width,pixi.renderer.screen.height);
      engine.current.clear();model.deltaTime=0;model.autoUpdate=oldAuto;this.running=false;this.onRestore();pixi.start();
    }
  }
}
