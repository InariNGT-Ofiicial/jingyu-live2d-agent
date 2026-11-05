import {checkValue} from './model-tools.mjs';
export async function probeParameter({model,app,id,value,soft,strict=false,signal}){
 const core=model.internalModel.coreModel,raw=core.getModel(),index=Array.from(raw.parameters.ids).indexOf(id);
 if(index<0)throw Error('模型没有参数 '+id);
 const p={id,min:raw.parameters.minimumValues[index],max:raw.parameters.maximumValues[index],default:raw.parameters.defaultValues[index]};
 const admitted=checkValue(p,value,soft,strict),old=Float32Array.from(raw.parameters.values),parts=Float32Array.from(raw.parts.opacities),auto=model.autoUpdate,started=app.ticker.started,oldDelta=model.deltaTime;
 const signature=()=>Array.from(raw.drawables.vertexPositions,a=>Array.from(a));
 const render=()=>{model.deltaTime=0;core.update();app.renderer.render(app.stage);};
 let result,baseline;
 try{
  app.stop();model.autoUpdate=false;render();baseline=signature();const before=core.getParameterValueById(id);
  core.setParameterValueById(id,admitted.value);render();const changed=signature();
  let vertexDelta=0;changed.forEach((a,i)=>a.forEach((v,j)=>{vertexDelta=Math.max(vertexDelta,Math.abs(v-baseline[i][j]));}));
  const observed=core.getParameterValueById(id);
  result={id,requested:value,applied:admitted.value,before,observed,vertexDelta,softExceeded:admitted.softExceeded,scope:'isolated-core-no-physics',visualSemantics:'unverified'};
  // Display the actual pose for inspection; cancellation always reaches restoration.
  await new Promise((resolve,reject)=>{
   if(signal?.aborted){reject(Error('探针已取消'));return;}
   const cancel=()=>{clearTimeout(timer);reject(Error('探针已取消'));};
   const timer=setTimeout(()=>{signal?.removeEventListener('abort',cancel);resolve();},800);
   signal?.addEventListener('abort',cancel,{once:true});
  });
  if(Math.abs(observed-admitted.value)>1e-4)throw Error('参数写入未生效');
 }finally{
  raw.parameters.values.set(old);raw.parts.opacities.set(parts);render();
  const delta=Math.max(...raw.parameters.values.map((v,i)=>Math.abs(v-old[i])));
  let geometryDelta=0;if(baseline)signature().forEach((a,i)=>a.forEach((v,j)=>{geometryDelta=Math.max(geometryDelta,Math.abs(v-baseline[i][j]));}));
  if(result){result.restoreDelta=delta;result.restoreGeometryDelta=geometryDelta;result.restored=delta<1e-5&&geometryDelta<1e-5;result.status=!result.restored?'restore-failed':result.vertexDelta>1e-6?'geometry-confirmed':'numeric-only';}
  model.deltaTime=oldDelta;model.autoUpdate=auto;if(started)app.start();
 }
 return result;
}
