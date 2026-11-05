const {Vec3}=require('vec3');
const {goals}=require('mineflayer-pathfinder');
const {inventory}=require('./survival-policy.cjs');
const vec=p=>new Vec3(p.x,p.y,p.z),sleep=ms=>new Promise(r=>setTimeout(r,ms));
module.exports=function({bot,memory:m,focus,event,check}){
 const posKey=p=>`${p.x},${p.y},${p.z}`;
 const item=re=>bot.inventory.items().find(i=>typeof re==='string'?i.name===re:re.test(i.name));
 const air=p=>['air','cave_air','void_air','short_grass','grass','tall_grass','snow'].includes(bot.blockAt(p)?.name);
 const solid=p=>bot.blockAt(p)?.boundingBox==='block';
 async function pause(ms){for(let t=0;t<ms;t+=100){check();await sleep(Math.min(100,ms-t));}check();}
 async function go(p,r=2){
  check();focus(vec(p).offset(.5,.5,.5),'移动目标');let timer;
  try{await Promise.race([bot.pathfinder.goto(new goals.GoalNear(p.x,p.y,p.z,r)),new Promise((_,reject)=>{timer=setTimeout(()=>{bot.pathfinder.setGoal(null);reject(Error('路径停滞，换一个目标'));},12000);})]);check();}
  finally{clearTimeout(timer);}
 }
 async function dig(b){
  check();const tool=bot.pathfinder.bestHarvestTool(b);if(tool)await bot.equip(tool,'hand');check();
  if(!b.canHarvest(bot.heldItem?.type??null))throw Error('缺少可采集 '+b.name+' 的工具');
  focus(b.position.offset(.5,.5,.5),'采集 '+b.name);await bot.dig(b);check();
 }
 async function pickup(p,before){
  await pause(350);
  const increased=()=>Object.entries(inventory(bot)).some(([k,v])=>v>(before[k]||0));
  if(!increased()){
   const dropped=Object.values(bot.entities).filter(e=>e.name==='item'&&e.position.distanceTo(p)<5).sort((a,b)=>a.position.distanceTo(bot.entity.position)-b.position.distanceTo(bot.entity.position))[0];
   await go(dropped?.position||vec(p).offset(0,Math.min(0,bot.entity.position.y-p.y),0),.8);await pause(700);
  }
  const after=inventory(bot);
  const gained=Object.fromEntries(Object.keys(after).filter(k=>after[k]>(before[k]||0)).map(k=>[k,after[k]-(before[k]||0)]));
  if(!Object.keys(gained).length)throw Error('未确认物品入背包');return {gained};
 }
 async function gather(resource){
  const re=resource==='log'?/_log$/:/^(stone|cobblestone)$/;
  const blocks=bot.findBlocks({matching:b=>re.test(b.name),maxDistance:40,count:40}).map(p=>bot.blockAt(p)).filter(b=>b&&
   !(m.blocked?.[posKey(b.position)]>Date.now())&&b.position.y>=bot.entity.position.y-(resource==='stone'?8:3)&&b.position.y<=bot.entity.position.y+4);
  const b=blocks[0];if(!b)return {missing:resource};
  m.target=posKey(b.position);const before=inventory(bot);await go(b.position);
  const current=bot.blockAt(b.position);if(current?.name===b.name)await dig(current);
  const receipt=await pickup(b.position,before);return {...receipt,position:b.position,block:b.name};
 }
 async function craft(name){
  let names=name==='planks'?bot.registry.itemsArray.filter(i=>/_planks$/.test(i.name)).map(i=>i.name):[name];
  let table=m.table?bot.blockAt(vec(m.table)):null;
  if(table?.name!=='crafting_table')table=null;
  if(table)await go(table.position);
  for(const n of names){
   const type=bot.registry.itemsByName[n]?.id;if(type===undefined)continue;
   const recipe=bot.recipesFor(type,null,1,table)[0];if(!recipe)continue;
   const before=inventory(bot)[n]||0;check();await bot.craft(recipe,1,table);await pause(200);
   const after=inventory(bot)[n]||0;if(after<=before)throw Error('合成后背包数量未增加');
   return {item:n,gained:after-before};
  }
  throw Error('没有可用的 '+name+' 配方或材料');
 }
 async function put(p,name){
  check();const held=item(name);if(!held)throw Error('缺少放置材料 '+name);
  if(!air(p))throw Error('放置位置被占用 '+posKey(p));
  const directions=[new Vec3(0,-1,0),new Vec3(1,0,0),new Vec3(-1,0,0),new Vec3(0,0,1),new Vec3(0,0,-1),new Vec3(0,1,0)];
  const d=directions.find(v=>solid(p.plus(v)));if(!d)throw Error('没有支撑面');
  const ref=bot.blockAt(p.plus(d));focus(p.offset(.5,.5,.5),'放置 '+name);await bot.equip(held,'hand');check();
  await bot.placeBlock(ref,d.scaled(-1));await pause(150);
  if(!bot.blockAt(p)?.name?.includes(name==='torch'?'torch':name))throw Error('放置未确认 '+name);
 }
 function site(radius=5,flat=false){
  const origin=bot.entity.position.floored();
  for(let r=flat?2:1;r<=radius;r++)for(let x=-r;x<=r;x++)for(let z=-r;z<=r;z++)for(const dy of [0,1,-1,2,-2]){
   if(Math.max(Math.abs(x),Math.abs(z))!==r)continue;const p=origin.offset(x,dy,z);
   let good=true;for(let dx=flat?-1:0;dx<=(flat?1:0);dx++)for(let dz=flat?-1:0;dz<=(flat?1:0);dz++){
    if(!solid(p.offset(dx,-1,dz))||![0,1,2].every(y=>air(p.offset(dx,y,dz))))good=false;
   }
   if(good)return p;
  }return null;
 }
 async function station(name){
  const p=site();if(!p)throw Error('附近没有可放置工作站的地面');await go(p,2);await put(p,name);
  m[name==='crafting_table'?'table':'furnace']=p;return {item:name,position:p};
 }
 async function smelt(inputName){
  const outputName=inputName?'cooked_'+inputName:'charcoal';
  const b=bot.blockAt(vec(m.furnace));if(b?.name!=='furnace'){m.furnace=null;throw Error('熔炉不在原位置');}
  await go(b.position);check();const f=await bot.openFurnace(b);let windowClosed=false;
  try{
   if(!f.outputItem()){
    if(!f.inputItem()){const input=item(inputName||/_log$/);if(!input)throw Error('缺少待烧制材料');await f.putInput(input.type,null,1);}
    if(!f.fuelItem()&&!(f.fuel>0)){const fuel=item(/_planks$/);if(!fuel)throw Error('缺少燃料');await f.putFuel(fuel.type,null,1);}
    for(let t=0;t<160&&!f.outputItem();t++)await pause(100);
   }
   const output=f.outputItem();if(!output)throw Error('未收到熔炉输出');
   const actual=output.name,before=inventory(bot)[actual]||0;await f.takeOutput();
   // Mineflayer copies the container's player slots into bot.inventory when it closes.
   f.close();windowClosed=true;await pause(200);
   if((inventory(bot)[actual]||0)<=before)throw Error('熔炉产物没有进入背包');return {item:actual,expected:outputName};
  }finally{if(!windowClosed)f.close();}
 }
 async function hunt(id){
  const e=bot.entities[id];if(!e||!['cow','pig','sheep','chicken'].includes(e.name))throw Error('食物目标已离开');
  const before=inventory(bot);let p=e.position.clone();
  for(let n=0;n<12&&bot.entities[id];n++){
   check();p=e.position.clone();await go(p,1.5);focus(e.position.offset(0,.6,0),'获取食物');
   const weapon=item(/_axe$/)||item(/_sword$/);if(weapon)await bot.equip(weapon,'hand');check();bot.attack(e);await pause(850);
  }
  if(bot.entities[id])throw Error('目标仍然存活');return pickup(p,before);
 }
 async function eat(name){
  const food=item(name);if(!food)throw Error('食物已耗尽');const before=bot.food;
  await bot.equip(food,'hand');check();await bot.consume();check();
  if(bot.food<=before)throw Error('进食后饥饿值未增加');return {foodBefore:before,foodAfter:bot.food};
 }
 async function explore(resource){
  // Search actual dry surfaces instead of walking arbitrary compass vectors into an ocean.
  const origin=bot.entity.position;m.exploration++;m.visited=m.visited||{};
  const cell=p=>`${Math.floor(p.x/6)},${Math.floor(p.z/6)}`;
  const candidates=bot.findBlocks({matching:b=>['grass_block','dirt','podzol','stone','sand','gravel'].includes(b.name),maxDistance:48,count:1500})
   .map(p=>p.offset(0,1,0)).filter(p=>p.distanceTo(origin)>6&&air(p)&&air(p.offset(0,1,0))&&!(m.visited[cell(p)]>Date.now()));
  candidates.sort((a,b)=>a.distanceTo(origin)-b.distanceTo(origin));
  const seen=new Set(),frontiers=candidates.filter(p=>{const key=cell(p);if(seen.has(key))return false;seen.add(key);return true;});
  let lastError='已加载范围内找不到新的陆地，暂停等待外部指引';
  for(const p of frontiers.slice(0,3)){
   m.visited[cell(p)]=Date.now()+180000;focus(p,'寻找 '+resource);
   try{await go(p,1);return {position:bot.entity.position,resource};}catch(e){check();lastError=e.message;}
  }
  throw Error(lastError);
 }
 function shape(p){const cells=[];for(let y=0;y<2;y++)for(let x=-1;x<=1;x++)for(let z=-1;z<=1;z++)if(x||z)cells.push(p.offset(x,y,z));
  for(let x=-1;x<=1;x++)for(let z=-1;z<=1;z++)cells.push(p.offset(x,2,z));return cells;}
 async function build(){
  const p=m.buildSite?vec(m.buildSite):site(7,true);if(!p)throw Error('附近没有三乘三平坦建造位置');
  m.buildSite=p;await go(p,.3);
  for(const cell of shape(p))if(!solid(cell)){
   const plank=item(/_planks$/);if(!plank)throw Error('庇护所材料不足');await put(cell,plank.name);
  }
  if(!bot.blockAt(p)?.name?.includes('torch'))await put(p,'torch');
  if(!shape(p).every(solid))throw Error('庇护所墙体或屋顶不完整');
  m.home=p;m.closed=true;m.buildSite=null;return {home:p,roofAndWalls:25,lit:true};
 }
 async function exit(){
  const p=vec(m.home);for(const y of [1,0]){const b=bot.blockAt(p.offset(1,y,0));if(b?.boundingBox==='block')await dig(b);}
  m.closed=false;await go(p.offset(2,0,0),.7);return {exit:true};
 }
 async function shelter(){
  const p=vec(m.home);await go(p,.3);
  for(const y of [0,1])if(!solid(p.offset(1,y,0))){const plank=item(/_planks$/);if(!plank)throw Error('没有封闭入口的木板');await put(p.offset(1,y,0),plank.name);}
  if(!shape(p).every(solid))throw Error('庇护所损坏，不能视作安全');m.closed=true;return {sheltered:true};
 }
 async function retreat(id){
  const enemy=bot.entities[id];if(!enemy)return {gone:true};const p=bot.entity.position;
  const away=p.minus(enemy.position);const length=Math.hypot(away.x,away.z)||1;
  await go(p.offset(away.x/length*12,0,away.z/length*12),2);return {distance:bot.entity.position.distanceTo(enemy.position)};
 }
 async function escape(shore=false){
  const before=bot.entity.position.clone();
  if(shore){
   const candidates=bot.findBlocks({matching:b=>['sand','gravel','dirt','grass_block','clay'].includes(b.name),maxDistance:3,count:30})
    .map(p=>bot.blockAt(p)).filter(b=>b.position.y>=Math.floor(before.y)&&b.position.y<=Math.floor(before.y)+1)
    .sort((a,b)=>a.position.distanceTo(before)-b.position.distanceTo(before));
   const b=candidates[0];
   if(b){await dig(b);await bot.lookAt(b.position.offset(.5,.7,.5),true);}
   else await bot.look(bot.entity.yaw+Math.PI/2,0,true);
  }
  bot.setControlState('jump',true);
  if(shore||!bot.entity.isInWater)bot.setControlState('forward',true);
  try{await pause(2000);}finally{bot.clearControlStates();}
  if(shore&&bot.entity.position.distanceTo(before)<.5)throw Error('岸边脱困仍未取得位移');
  return {position:bot.entity.position,oxygen:bot.entity.metadata?.[1]};
 }
 return async decision=>{
  const {skill,args}=decision;
  const handlers={gather:()=>gather(args.resource),craft:()=>craft(args.item),station:()=>station(args.item),smelt:()=>smelt(args.input),
   hunt:()=>hunt(args.entity),eat:()=>eat(args.item),explore:()=>explore(args.resource),build,exit,shelter,
   retreat:()=>retreat(args.entity),escape:()=>escape(args.shore),wait:async()=>{await pause(4000);return {waited:true};}};
  if(!handlers[skill])throw Error('未知生存技能 '+skill);return handlers[skill]();
 };
};
