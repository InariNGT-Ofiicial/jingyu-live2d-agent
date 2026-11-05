// Real-server integration fixture. Never opens or changes the user's survival save.
const fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process');
const mineflayer=require('mineflayer'),{pathfinder,Movements}=require('mineflayer-pathfinder');
const root=path.resolve(__dirname,'..'),runtime=require('../.local/minecraft/runtime.json');
const folder=path.join(root,'.local/checks/minecraft/survival-fixture');fs.mkdirSync(folder,{recursive:true});
fs.writeFileSync(path.join(folder,'eula.txt'),'eula=true\n');
fs.writeFileSync(path.join(folder,'server.properties'),'server-ip=127.0.0.1\nserver-port=25567\nonline-mode=false\nenforce-secure-profile=false\nlevel-type=minecraft:flat\nlevel-name=fixture\ngenerate-structures=false\ngamemode=survival\ndifficulty=normal\nspawn-protection=0\nview-distance=3\nsimulation-distance=3\n');
const java=spawn(runtime.java,['-Xms256M','-Xmx1024M','-jar',runtime.jar,'nogui'],{cwd:folder,windowsHide:true,stdio:['pipe','pipe','pipe']});
const log=fs.createWriteStream(path.join(folder,'server.log'),{flags:'a'});java.stdout.pipe(log);java.stderr.pipe(log);
const command=c=>java.stdin.write(c+'\n'),sleep=ms=>new Promise(r=>setTimeout(r,ms));
const resume=process.env.JINGYU_QA_RESUME==='1';
const memoryFile=path.join(folder,'survival-memory.json');if(!resume){if(fs.existsSync(memoryFile))fs.copyFileSync(memoryFile,path.join(folder,'previous-memory.json'));fs.writeFileSync(memoryFile,'{}');}
let bot,closed=false;const state={},events=resume&&fs.existsSync(path.join(folder,'result.json'))?JSON.parse(fs.readFileSync(path.join(folder,'result.json'))).events:[];
async function main(){
 await new Promise((resolve,reject)=>{let text='';java.stdout.on('data',b=>{text+=b;if(text.includes('Done ('))resolve();});java.once('error',reject);java.once('exit',c=>reject(Error('Java exited '+c)));});
 bot=mineflayer.createBot({host:'127.0.0.1',port:25567,username:'SurvivalQA',auth:'offline',version:'1.20.1'});bot.loadPlugin(pathfinder);
 await new Promise((resolve,reject)=>{bot.once('spawn',resolve);bot.once('error',reject);});
 if(!resume)for(const c of ['gamerule doDaylightCycle false','gamerule doWeatherCycle false','gamerule doMobSpawning false','time set day','weather clear',
  'kill @e[type=!player]','fill -20 -60 -20 20 -50 20 air','fill -20 -61 -20 20 -61 20 grass_block',
  'fill -9 -60 -7 -6 -58 -4 oak_log','fill 5 -60 -7 8 -58 -4 stone','clear SurvivalQA','tp SurvivalQA 0.5 -60 0.5',
  'summon cow 7 -60 7 {NoAI:1b}','summon cow 8 -60 7 {NoAI:1b}','summon cow 9 -60 7 {NoAI:1b}','summon cow 10 -60 7 {NoAI:1b}'])command(c);
 await sleep(1200);await bot.waitForChunksToLoad();
 const movement=new Movements(bot);movement.canDig=true;movement.allow1by1towers=false;movement.allowSprinting=false;bot.pathfinder.setMovements(movement);
 const controller=require('./survival.cjs')({bot,folder,state,event:(type,data)=>{events.push({type,...data});if(type==='decision'||type==='survival-result')console.log(JSON.stringify({type,...data}));},focus:()=>{},say:async()=>{},check:()=>{if(closed)throw Error('stopped');},clearAttention:()=>{}});
 const interfacesOnly=process.env.JINGYU_QA_SCOPE==='interfaces';
 let result;
 if(interfacesOnly){
  const execute=require('./survival-skills.cjs')({bot,memory:controller.status.memory,focus:()=>{},event:()=>{},check:()=>{if(closed)throw Error('stopped');}});
  const run=async(skill,args={})=>{const receipt=await execute({skill,args});events.push({type:'survival-result',skill,status:'verified',result:receipt});console.log(JSON.stringify({skill,result:receipt}));};
  const inv=()=>require('./survival-policy.cjs').inventory(bot);
  await run('gather',{resource:'log'});
  if(!Object.keys(inv()).some(n=>/_planks$/.test(n)))await run('craft',{item:'planks'});
  if(!Object.keys(inv()).some(n=>/_log$/.test(n)))await run('gather',{resource:'log'});
  await run('smelt');await run('craft',{item:'torch'});
  result={status:'verified',scope:'interfaces-only',observation:controller.observe()};
 }else result=await controller.run({goal:'starter',maxSteps:160,maxMinutes:12});
 fs.writeFileSync(path.join(folder,'result.json'),JSON.stringify({kind:'controlled-real-server-fixture',result,events},null,2));
 const verified=new Set(events.filter(e=>e.type==='survival-result'&&e.status==='verified').map(e=>e.skill));
 if(interfacesOnly){
  for(const skill of ['gather','craft','station','smelt'])if(!verified.has(skill))throw Error('Missing interface receipt '+skill);
  const inv=require('./survival-policy.cjs').inventory(bot);if(!(inv.torch>0))throw Error('Torch craft was not confirmed');
  fs.writeFileSync(path.join(folder,'checks.json'),JSON.stringify({scope:'interfaces-only',verified:[...verified],inventory:inv,fullSurvival:false},null,2));
  console.log('SURVIVAL INTERFACES PASSED: collection, crafting, stations, smelting and torches');return;
 }
 if(result.status!=='completed')throw Error('Starter failed: '+result.status+' '+result.error);
 for(const skill of ['gather','craft','station','smelt','build','exit','hunt'])if(!verified.has(skill))throw Error('Missing skill receipt '+skill);
 // Force hunger only in this isolated fixture, then require real consumption to restore it.
 command('effect give SurvivalQA minecraft:hunger 3 255 true');await sleep(3500);
 const eating=await controller.run({goal:'sustain',maxSteps:1,maxMinutes:1});
 if(!eating.receipts.some(r=>r.skill==='eat'&&r.status==='verified'))throw Error('Eating receipt missing');
 command('time set night');await sleep(300);
 const shelter=await controller.run({goal:'return-home',maxSteps:8,maxMinutes:2});
 if(shelter.status!=='completed'||!shelter.memory.closed)throw Error('Night shelter not confirmed');
 fs.writeFileSync(path.join(folder,'checks.json'),JSON.stringify({starter:'completed',eating:eating.receipts,nightShelter:shelter.receipts,inventory:require('./survival-policy.cjs').inventory(bot)},null,2));
 console.log('SURVIVAL FIXTURE PASSED: real crafting, collection, smelting, shelter, food and night return');
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;}).finally(async()=>{closed=true;bot?.quit();command('stop');await sleep(5000);if(java.exitCode===null)java.kill();});
