import {MotionEngine} from './engine.mjs';
export class FrameExporter{
  constructor({api,clientId,onProgress,getRenderer}){Object.assign(this,{api,clientId,onProgress,getRenderer});this.active=null;}
  async run(job){
    if(job.clientId!==this.clientId||this.active)return;
    this.active=job.id;let scene,target,model;
    try{
      this.onProgress(job,'准备透明画布');
      // Cubism 4 keeps a shared shader singleton. A second WebGL context can
      // invalidate the live stage, so render a separate model into an offscreen
      // texture using the stage's existing context instead.
      const renderer=this.getRenderer();if(!renderer)throw Error('舞台渲染器尚未就绪');
      scene=new PIXI.Container();target=PIXI.RenderTexture.create({width:job.width,height:job.height,resolution:1});
      model=await PIXI.live2d.Live2DModel.from('/model/大肥鱼.model3.json',{autoUpdate:false,autoInteract:false,motionPreload:'NONE'});scene.addChild(model);
      const fit=Math.min(job.width*.88/model.internalModel.originalWidth,job.height*.94/model.internalModel.originalHeight);
      model.scale.set(fit);model.anchor.set(.5,0);model.position.set(job.width/2,job.height*.03);
      const profile=await this.api('/data/model-profile.json');const engine=new MotionEngine(model.internalModel.coreModel,profile,()=>{});
      model.internalModel.eyeBlink=undefined;model.internalModel.breath=undefined;model.internalModel.updateFocus=()=>{};
      let dt=1000/60,clock=0;model.internalModel.updateNaturalMovements=()=>engine.tick(dt);
      // Warm physics, then use the same initial motion phase for every export.
      for(let i=0;i<60;i++){clock+=dt;model.internalModel.update(dt,clock);}
      engine.clock=0;engine.current.clear();engine.start({id:job.id,compiled:job.compiled});let motionTime=0;
      for(let i=0;i<job.frameCount;i++){
        if(this.active!==job.id)throw Error('导出已取消');
        const targetTime=i/job.fps;
        while(motionTime<targetTime-1e-8){dt=Math.min(1000/60,(targetTime-motionTime)*1000);clock+=dt;model.internalModel.update(dt,clock);motionTime+=dt/1000;}
        if(i===0){dt=0;model.internalModel.update(0,clock);}
        renderer.render(scene,{renderTexture:target,clear:true});
        const png=renderer.plugins.extract.canvas(target).toDataURL('image/png').split(',')[1];
        await this.api('/api/export/frame',{id:job.id,clientId:this.clientId,token:job.token,index:i,png});
        if(i%job.fps===0)this.onProgress({...job,progress:(i+1)/job.frameCount*.8},`渲染 ${i+1} / ${job.frameCount} 帧`);
      }
      this.onProgress({...job,progress:.8},'正在编码文件');
    }catch(e){await this.api('/api/export/error',{id:job.id,clientId:this.clientId,token:job.token,error:e.message}).catch(()=>{});if(this.active===job.id){try{this.onProgress(await this.api(`/api/export?id=${job.id}`));}catch{this.onProgress({...job,status:'error',error:e.message});}}}
    finally{scene?.destroy({children:true,texture:false,baseTexture:false});target?.destroy(true);if(this.active===job.id)this.active=null;}
  }
}
