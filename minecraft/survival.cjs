const fs=require('node:fs'),path=require('node:path');
const {observe,decide,HOSTILES}=require('./survival-policy.cjs');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
module.exports=function({bot,folder,state,event,focus,say,check,clearAttention}){
 const file=path.join(folder,'survival-memory.json');
 let m=fs.existsSync(file)?JSON.parse(fs.readFileSync(file,'utf8')):{};
 m={exploration:0,blocked:{},...m};
 const status=state.survival={status:'idle',goal:'starter',step:0,decision:null,observation:null,receipts:[],memory:m};
 let reason=null,fatal=false,activeSkill=null,voiceBusy=false,lastCue=null,lastVoiceAt=0;
 const save=()=>fs.writeFileSync(file,JSON.stringify(m,null,2));
 const abort=()=>{bot.pathfinder.setGoal(null);bot.stopDigging();bot.clearControlStates();bot.deactivateItem();if(bot.currentWindow)bot.closeWindow(bot.currentWindow);};
 const guardedCheck=()=>{check();if(fatal)throw Error('角色已死亡');if(reason)throw Error(reason);};
 const execute=require('./survival-skills.cjs')({bot,memory:m,focus,event,check:guardedCheck});
 function refresh(){
  for(const [key,name]of [['table','crafting_table'],['furnace','furnace']])if(m[key]){
   const {Vec3}=require('vec3');const p=m[key],b=bot.blockAt(new Vec3(p.x,p.y,p.z));
   if(b&&b.name!==name)m[key]=null;
  }
  return status.observation=observe(bot,m);
 }
 function narrate(d){
  if(voiceBusy||(d.cue===lastCue&&Date.now()-lastVoiceAt<12000)||Date.now()-lastVoiceAt<4500)return;
  voiceBusy=true;lastCue=d.cue;lastVoiceAt=Date.now();
  // Voice does not block emergency actions; one pending line, never an unbounded queue.
  say(d.cue,true).finally(()=>{voiceBusy=false;});
 }
 function monitor(){
  if(!activeSkill)return;const s=refresh();
  if(s.health<=0){fatal=true;reason='角色已死亡';}
  else if(!['escape','retreat','shelter'].includes(activeSkill)){
   if(s.hazard||s.oxygen<8)reason='紧急避险';
   else if(s.danger?.distance<6&&!s.shelter?.closed)reason='敌对生物接近';
   else if(s.food<=6&&!['eat','hunt','explore'].includes(activeSkill))reason='饥饿打断';
  }
  if(reason)abort();
 }
 const death=()=>{fatal=true;reason='角色已死亡';abort();};
 return {
  status,observe:refresh,
  async run(options={}){
   const goal=options.goal||'starter',maxSteps=Number(options.maxSteps??160),maxMinutes=Number(options.maxMinutes??15);
   if(!['starter','sustain','return-home'].includes(goal)||!Number.isInteger(maxSteps)||maxSteps<1||maxSteps>1000||!Number.isFinite(maxMinutes)||maxMinutes<.1||maxMinutes>120)throw Error('生存目标或执行预算无效');
   status.status='running';status.goal=goal;status.startedAt=Date.now();status.step=0;status.error=null;status.receipts=[];
   fatal=false;let failures=0;const deadline=Date.now()+maxMinutes*60000,watch=setInterval(monitor,250);bot.on('death',death);
   try{
    for(let i=0;i<maxSteps&&Date.now()<deadline;i++){
     check();reason=null;activeSkill=null;const before=refresh();status.step=i+1;
     if(fatal){status.status='dead';status.error='角色已死亡；重新开始前检查存档和背包';break;}
     let d=decide(before,m,goal);
     if(m.recover&&!['retreat','escape','eat','halt'].includes(d.skill)){d={...d,skill:'escape',args:{shore:true},cue:'danger',reason:'水岸寻路停滞，尝试清理台阶并脱困'};m.recover=false;}
     if(m.relocate&&!['retreat','escape','eat','halt','shelter','wait'].includes(d.skill)){d={...d,skill:'explore',args:{resource:m.relocate},cue:'explore',reason:'上一位置不可用，先寻找新的工作位置'};m.relocate=null;}
     if(d.skill==='gather'&&m.missing===d.args.resource){d={...d,skill:'explore',cue:'explore',reason:'附近没有可达的 '+m.missing+'，更换搜索区域'};m.missing=null;}
     status.decision=d;event('decision',{step:i+1,...d});narrate(d);
     if(d.skill==='complete'){status.status='completed';break;}
     if(d.skill==='halt'){status.status=before.health<=0?'dead':'needs-attention';status.error=d.reason;break;}
     activeSkill=d.skill;const began=Date.now();
     let timeout;
     try{
      const result=await Promise.race([execute(d),new Promise((_,reject)=>{timeout=setTimeout(()=>{reason='技能执行超时';abort();reject(Error(reason));},45000);})]);
      guardedCheck();m.target=null;if(result.missing)m.missing=result.missing;
      const receipt={step:i+1,skill:d.skill,status:result.missing?'missing':'verified',durationMs:Date.now()-began,result,at:Date.now()};
      status.receipts.push(receipt);event('survival-result',receipt);failures=result.missing?failures+1:0;
      if(goal==='return-home'&&result.sheltered){status.status='completed';break;}
     }catch(e){
      check();abort();const interrupted=['紧急避险','敌对生物接近','饥饿打断'].includes(reason);
      const receipt={step:i+1,skill:d.skill,status:interrupted?'interrupted':'failed',error:e.message,at:Date.now()};
      status.receipts.push(receipt);event('survival-result',receipt);
      if(m.target){m.blocked[m.target]=Date.now()+120000;m.target=null;}
      if(!interrupted)failures++;
      if(fatal){status.status='dead';status.error=e.message;break;}
      if(failures>=4){status.status='needs-attention';status.error='连续四次未取得进展：'+e.message;break;}
      if(!interrupted&&d.skill==='gather')m.missing=d.args.resource;
      if(!interrupted&&['gather','explore'].includes(d.skill)&&bot.entity.isInWater)m.recover=true;
      if(!interrupted&&['station','build'].includes(d.skill))m.relocate='平坦地面';
      // An unsuccessful skill always returns to observation instead of replaying its tail.
      await sleep(300);
     }finally{clearTimeout(timeout);activeSkill=null;save();status.receipts=status.receipts.slice(-40);}
    }
    if(status.status==='running')status.status='paused';
    return status;
   }catch(e){status.status='cancelled';throw e;}
   finally{clearInterval(watch);bot.removeListener('death',death);activeSkill=null;abort();refresh();clearAttention();save();status.finishedAt=Date.now();}
  }
 };
};
