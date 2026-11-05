const {Vec3}=require('vec3');
const {goals}=require('mineflayer-pathfinder');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
module.exports=function({bot,state,event,focus,say,check,prepareArena}){
 const inventory=()=>Object.fromEntries(bot.inventory.items().map(i=>[i.name,bot.inventory.items().filter(x=>x.name===i.name).reduce((n,x)=>n+x.count,0)]));
 const block=(name)=>{const b=bot.findBlock({matching:b=>b.name===name,maxDistance:24});if(!b)throw Error('附近没有 '+name);return b;};
 async function walk(target){
  check();focus(target.offset(.5,.5,.5),'接近目标');await say('walk');check();
  event('moving',{target});await bot.pathfinder.goto(new goals.GoalNear(target.x,target.y,target.z,2));check();
  event('arrived',{position:bot.entity.position});
 }
 async function inspect(name){
  const b=block(name);focus(b.position.offset(.5,.5,.5),b.name);
  await say('inspect');check();await sleep(700);check();
  await bot.lookAt(b.position.offset(.5,.5,.5),false);event('observed',{block:b.name,position:b.position});return b;
 }
 async function dig(name){
  let b=await inspect(name);await walk(b.position);check();b=bot.blockAt(b.position);
  const tool=bot.inventory.items().find(i=>i.name===(name==='stone'?'iron_pickaxe':'iron_axe'));
  if(tool)await bot.equip(tool,'hand');check();
  const before=inventory();focus(b.position.offset(.5,.5,.5),'采集 '+b.name);
  await say('dig');check();event('digging',{block:b.name,position:b.position,before});
  await bot.dig(b);check();await bot.pathfinder.goto(new goals.GoalNear(b.position.x,b.position.y,b.position.z,.7));
  await sleep(700);check();const after=inventory();
  const gained=Object.keys(after).filter(k=>(after[k]||0)>(before[k]||0));
  if(!gained.length)throw Error('方块已挖开，但未确认拾取入背包');
  event('collected',{before,after,gained});await say('collected',true);
 }
 async function place(){
  const destination=new Vec3(2,-60,-2);await walk(destination);check();
  const support=bot.blockAt(destination.offset(0,-1,0)),item=bot.inventory.items().find(i=>i.name==='oak_planks');
  if(!item||!support||bot.blockAt(destination).name!=='air')throw Error('缺少木板或放置位置已占用');
  focus(destination.offset(.5,.5,.5),'放置木板');await say('place');check();
  await bot.equip(item,'hand');await bot.placeBlock(support,new Vec3(0,1,0));check();
  await sleep(250);if(bot.blockAt(destination).name!=='oak_planks')throw Error('未收到木板放置结果');
  event('placed',{position:destination,block:'oak_planks'});await say('placed',true);
 }
 return async function run(action,name='oak_log'){
  if(action==='demo'){await prepareArena();check();await dig('oak_log');await dig('stone');await place();await say('done',true);}
  else if(action==='inspect')await inspect(name);
  else if(action==='walk')await walk(block(name).position);
  else if(action==='dig')await dig(name);
  else if(action==='place')await place();
  else throw Error('未知游戏动作');
 };
};
