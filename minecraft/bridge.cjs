const fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const {spawn}=require('node:child_process');
const mineflayer=require('mineflayer'),{pathfinder,Movements}=require('mineflayer-pathfinder');
require('./patch-viewer.cjs')();
const {mineflayer:viewer}=require('prismarine-viewer');
const {project}=require('./attention.cjs');
const root=path.resolve(__dirname,'..'),folder=path.join(root,'.local/minecraft');
const mode=process.env.JINGYU_MINECRAFT_WORLD||'demo';
const runtime=require('./world-config.cjs')(JSON.parse(fs.readFileSync(path.join(folder,'runtime.json'))),folder,mode),catalog=require('./cues.json');
const studio=process.env.JINGYU_STUDIO_URL||'http://127.0.0.1:61944';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const state={ready:false,server:'starting',version:runtime.version,kind:'vanilla-local-test',mode,viewerUrl:'http://127.0.0.1:61947',events:[],attention:null,run:null,narration:null,error:null};
let bot,java,survival,currentId=null,clientId=null,target=null,lastSpeech=null,seq=0,closing=false,activeTask=false;
async function api(route,data){
 const r=await fetch(studio+route,{method:data?'POST':'GET',headers:{'Content-Type':'application/json'},body:data?JSON.stringify(data):undefined,signal:AbortSignal.timeout(12000)});
 const value=await r.json();if(!r.ok)throw Error(value.error||r.statusText);return value;
}
function event(type,data={}){
 const e={seq:++seq,type,at:Date.now(),...data};state.events.push(e);if(state.events.length>80)state.events.shift();
 fs.appendFileSync(path.join(folder,'events.jsonl'),JSON.stringify(e)+'\n');return e;
}
function snapshot(){
 const entity=bot?.entity;
 if(entity&&target){const eye=entity.position.offset(0,1.6,0);state.attention={...target,screen:project(target.position,eye,entity.yaw,entity.pitch,{aspect:4/3}),camera:{eye,yaw:entity.yaw,pitch:entity.pitch,fov:75,aspect:4/3}};}
 else state.attention=null;
 if(survival&&state.ready)survival.observe();
 return {...state,health:bot?.health,food:bot?.food,time:bot?.time?.timeOfDay,position:entity?.position,inventory:bot?.inventory.items().map(i=>({name:i.name,count:i.count}))||[]};
}
function focus(position,label){target={position,label};event('attention',target);bot.viewer?.drawBoxGrid('attention',position.offset(-.5,-.5,-.5),position.offset(.5,.5,.5),'aqua');}
function clearAttention(){target=null;state.attention=null;bot?.viewer?.erase('attention');}
async function waitSpeech(jobId,started=false){
 for(let i=0;i<90;i++){
  const data=await api('/api/studio/state'),job=data.jobs.find(j=>j.id===jobId);
  if(!job)throw Error('语音回执已丢失');
  if(['error','interrupted'].includes(job.status))throw Error(job.error||'语音已中断');
  if(job.status==='completed'||started&&job.status==='playing')return job;
  if(!currentId)throw Error('已停止');await sleep(100);
 }
 throw Error('语音播放确认超时');
}
async function say(key,finish=false){
 const cue=catalog[key]||catalog.inspect;state.narration={text:cue.text,requestedAt:Date.now(),status:'text-only'};
 if(!clientId)return;
 const mine=currentId;
 try{
  if(lastSpeech)await waitSpeech(lastSpeech);if(currentId!==mine)throw Error('已停止');
  const cached=fs.existsSync(path.join(folder,'cues.json'))?JSON.parse(fs.readFileSync(path.join(folder,'cues.json')))[key]:null;
  const job=cached?await api('/api/studio/command',{clientId,action:'play',audio:'speech',speechId:cached.speechId}):await api('/api/studio/speak',{clientId,text:cue.text,performance:{emotion:cue.emotion,intensity:.45}});
  if(currentId!==mine){await api('/api/studio/command',{clientId,action:'stop'});return;}
  lastSpeech=job.id;state.narration.status='preparing';state.narration.cached=!!cached;
  await waitSpeech(job.id,true);state.narration.status='playing';state.narration.playedAt=Date.now();
  event('narration',{key,...state.narration,jobId:job.id,delayMs:state.narration.playedAt-state.narration.requestedAt});
  if(finish){await waitSpeech(job.id);state.narration.status='completed';}
 }catch(e){if(currentId!==mine)return;state.narration.status='error';state.narration.error=e.message;event('voice-error',{message:e.message});}
}
function consoleCommand(command){java.stdin.write(command+'\n');}
async function prepareArena(){
 if(mode!=='demo')throw Error('生存存档禁止重置试验场');
 target=null;state.attention=null;bot.viewer?.erase('attention');
 for(const command of ['gamerule doDaylightCycle false','gamerule doWeatherCycle false','gamerule doMobSpawning false','time set day','weather clear',
  'fill -12 -60 -12 12 -55 12 air','fill -12 -61 -12 12 -61 12 grass_block','setblock -4 -60 -5 oak_log','setblock 4 -60 -5 stone',
  'tp Jingyu 0.5 -60 0.5 180 0','clear Jingyu','give Jingyu iron_axe','give Jingyu iron_pickaxe','give Jingyu oak_planks 5'])consoleCommand(command);
 await sleep(1000);await bot.look(0,0,true);await bot.waitForChunksToLoad();event('arena-ready');
}
function cancel(){
 const run=state.run;currentId=null;bot?.pathfinder.stop();bot?.pathfinder.setGoal(null);bot?.stopDigging();bot?.clearControlStates();clearAttention();
 if(run?.status==='running')run.status='cancelled';
 if(state.narration)state.narration.status='interrupted';
 if(clientId&&lastSpeech)api('/api/studio/command',{clientId,action:'stop'}).catch(()=>{});
 lastSpeech=null;event('stopped');
}
async function startAction(data){
 if(!state.ready)throw Error('Minecraft 尚未就绪');
 if(data.action==='stop'){cancel();return snapshot();}
 if(currentId||activeTask)throw Error('已有游戏动作正在执行或停止中');
 if(!['demo','inspect','walk','dig','place','survival','survival-step'].includes(data.action))throw Error('未知动作');
 const isSurvival=data.action.startsWith('survival');
 if(isSurvival&&mode!=='survival')throw Error('请关闭试验场并启动普通生存世界');
 if(!isSurvival&&mode!=='demo')throw Error('固定演示只在试验场运行，请使用生存决策');
 if(isSurvival&&(!['starter','sustain','return-home'].includes(data.goal||'starter')||!Number.isInteger(Number(data.maxSteps??160))||Number(data.maxSteps??160)<1||Number(data.maxSteps??160)>1000||!Number.isFinite(Number(data.maxMinutes??15))||Number(data.maxMinutes??15)<.1||Number(data.maxMinutes??15)>120))throw Error('生存目标或执行预算无效');
 const name=data.block||'oak_log';if(!['oak_log','stone'].includes(name))throw Error('首轮只支持 oak_log / stone');
 clientId=data.clientId||null;lastSpeech=null;const id=String(Date.now());currentId=id;activeTask=true;
 state.run={id,action:data.action,block:name,status:'running',startedAt:Date.now()};state.error=null;
 const check=()=>{if(currentId!==id)throw Error('已停止');};
 const run=require('./actions.cjs')({bot,state,event,focus,say,check,prepareArena});
 if(isSurvival&&!survival)survival=require('./survival.cjs')({bot,folder:runtime.cwd,state,event,focus,say,check:()=>{if(!currentId)throw Error('已停止');},clearAttention});
 const timer=isSurvival?null:setTimeout(()=>{if(currentId===id){cancel();state.run.status='error';state.run.error='游戏动作超时';}},data.action==='demo'?180000:45000);
 const execution=isSurvival?survival.run({...data,maxSteps:data.action==='survival-step'?1:data.maxSteps}):run(data.action,name);
 execution.then(result=>{check();state.run.status=isSurvival?result.status:'completed';state.run.finishedAt=Date.now();event(state.run.status,{id});}).catch(async e=>{
  if(currentId===id){state.run.status='error';state.run.error=e.message;bot.pathfinder.setGoal(null);bot.clearControlStates();event('action-error',{message:e.message});await say('failed',true);}
 }).finally(()=>{clearTimeout(timer);activeTask=false;if(currentId===id)currentId=null;});
 return state.run;
}
async function shutdown(){
 if(closing)return;closing=true;cancel();bot?.quit();bot?.viewer?.close();
 if(java?.exitCode===null)consoleCommand('stop');
 setTimeout(()=>{if(java?.exitCode===null)java.kill();process.exit(0);},7000).unref();
}
const control=http.createServer(async(req,res)=>{
 res.setHeader('Content-Type','application/json');res.setHeader('Cache-Control','no-store');
 try{
  if(req.method==='GET'&&req.url==='/state'){res.end(JSON.stringify(snapshot()));return;}
  if(req.method!=='POST')throw Error('Unknown route');
  let body='';for await(const chunk of req){body+=chunk;if(body.length>8000)throw Error('请求过长');}
  if(req.url==='/shutdown'){res.end('{"ok":true}');await shutdown();return;}
  if(req.url!=='/action')throw Error('Unknown route');
  res.end(JSON.stringify(await startAction(JSON.parse(body||'{}'))));
 }catch(e){res.statusCode=400;res.end(JSON.stringify({error:e.message}));}
});
control.listen(61946,'127.0.0.1',()=>console.log('Minecraft bridge http://127.0.0.1:61946'));
java=spawn(runtime.java,['-Xms512M','-Xmx1536M','-jar',runtime.jar,'nogui'],{cwd:runtime.cwd,windowsHide:true,stdio:['pipe','pipe','pipe']});
const log=fs.createWriteStream(path.join(folder,'server-console.log'),{flags:'a'});java.stdout.pipe(log);java.stderr.pipe(log);
let consoleBuffer='';
java.stdout.on('data',chunk=>{
 consoleBuffer+=chunk.toString();if(consoleBuffer.length>16000)consoleBuffer=consoleBuffer.slice(-16000);
 if(!bot&&consoleBuffer.includes('Done (')){
  state.server='ready';bot=mineflayer.createBot({host:runtime.host,port:runtime.port,username:'Jingyu',auth:'offline',version:runtime.version});
  bot.loadPlugin(pathfinder);
  bot.on('error',e=>{state.error=e.message;event('bot-error',{message:e.message});});
  bot.on('kicked',reason=>{state.error=String(reason);state.ready=false;event('kicked',{reason});});
  bot.on('end',reason=>{state.ready=false;event('disconnected',{reason});});
  bot.once('spawn',async()=>{
   try{
    const movements=new Movements(bot);movements.canDig=mode==='survival';movements.allow1by1towers=false;movements.allowParkour=false;movements.allowSprinting=false;movements.maxDropDown=2;movements.liquidCost=8;movements.entitiesToAvoid=require('./survival-policy.cjs').HOSTILES;bot.pathfinder.setMovements(movements);
    viewer(bot,{port:{port:61947,host:'127.0.0.1'},firstPerson:true,viewDistance:4});
    if(mode==='demo')await prepareArena();else await bot.waitForChunksToLoad();state.ready=true;event('ready',{mode});
   }catch(e){state.error=e.message;event('setup-error',{message:e.message});}
  });
 }
});
java.on('error',e=>{state.server='error';state.error=e.message;});
java.on('exit',code=>{state.server='stopped';state.ready=false;if(!closing)state.error='Java server exited: '+code;else process.exit(0);});
process.on('SIGINT',shutdown);process.on('SIGTERM',shutdown);
