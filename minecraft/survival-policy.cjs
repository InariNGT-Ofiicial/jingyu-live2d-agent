// Pure decision policy: one observable, verifiable skill at a time. No console commands.
const LOG=/_log$/,PLANK=/_planks$/;
const FOOD=['cooked_beef','cooked_porkchop','cooked_mutton','cooked_chicken','bread','apple','carrot','baked_potato','sweet_berries','beef','porkchop','mutton'];
const HOSTILES=new Set(['zombie','husk','drowned','skeleton','stray','creeper','spider','cave_spider','witch','pillager','vindicator','slime','phantom']);
const sum=(inv,re)=>Object.entries(inv).reduce((n,[k,v])=>n+(re.test(k)?v:0),0);
function inventory(bot){const out={};for(const i of bot.inventory.items())out[i.name]=(out[i.name]||0)+i.count;return out;}
function observe(bot,memory){
 const p=bot.entity.position,inv=inventory(bot),feet=bot.blockAt(p),head=bot.blockAt(p.offset(0,1,0));
 const entities=Object.values(bot.entities).filter(e=>e!==bot.entity&&e.position).map(e=>({id:e.id,name:e.name,distance:p.distanceTo(e.position),position:e.position}));
 const hostiles=entities.filter(e=>HOSTILES.has(e.name)&&e.distance<20).sort((a,b)=>a.distance-b.distance);
 // 1.20.1 entity metadata slot 1 is this player's air supply (ticks / 15).
 // Mineflayer 4.39's shared oxygenLevel is also updated by other entities, including squid.
 const oxygen=Math.max(0,Math.min(20,Math.round((bot.entity.metadata?.[1]??300)/15)));
 return {at:Date.now(),health:bot.health,food:bot.food,oxygen,position:p,inventory:inv,
  time:bot.time.timeOfDay,night:bot.time.timeOfDay>=12500&&bot.time.timeOfDay<23500,
  danger:hostiles[0]||null,inWater:!!bot.entity.isInWater,hazard:[feet?.name,head?.name].some(n=>['lava','fire','soul_fire'].includes(n)),
  animals:entities.filter(e=>['cow','pig','sheep','chicken'].includes(e.name)&&e.distance<32),
  shelter:memory.home?{position:memory.home,closed:!!memory.closed,distance:p.distanceTo(memory.home)}:null};
}
function decide(s,m,goal='starter'){
 const inv=s.inventory,planks=sum(inv,PLANK),logs=sum(inv,LOG),hasPick=Object.keys(inv).some(k=>/_pickaxe$/.test(k)),
  edible=FOOD.find(n=>inv[n]),foodCount=FOOD.reduce((n,k)=>n+(inv[k]||0),0);
 const step=(skill,reason,args={},cue=skill)=>({skill,args,reason,cue,goal});
 if(s.health<=0)return step('halt','角色已死亡，暂停并等待重新开始');
 if(s.hazard||s.oxygen<8)return step('escape','进入危险方块或氧气不足，先离开危险区域',{},'danger');
 if(s.danger&&s.danger.distance<8&&!(s.shelter?.closed&&s.shelter.distance<1.5))return step('retreat','附近有 '+s.danger.name+'，先拉开距离',{entity:s.danger.id},'danger');
 if(s.food<=16&&edible)return step('eat','饥饿值 '+s.food+'，先补充食物',{item:edible});
 if(s.food<=6&&!edible)return s.animals.length?step('hunt','食物不足，寻找附近动物获取食物',{entity:s.animals[0].id},'hunt'):step('explore','食物不足，寻找食物来源',{resource:'food'},'explore');
 if(s.shelter?.closed){
  if(s.night||s.health<10)return step('wait','在庇护所等待天亮或恢复生命',{},'shelter');
  return step('exit','白天到来，打开庇护所出口',{},'explore');
 }
 if(s.night&&s.shelter)return step('shelter','天黑了，回到已建庇护所',{},'shelter');
 if(goal==='return-home')return s.shelter?step('shelter','按目标返回庇护所',{},'shelter'):step('halt','尚未建立营地，先执行开局目标');
 // Resolve crafting dependencies against current inventory, not a memorized action sequence.
 function need(name,count=1,chain=[]){
  if(name==='furnace'&&m.furnace)return null;
  const have=name==='planks'?planks:name==='log'?logs:(inv[name]||0);if(have>=count)return null;
  const reason=[...chain,`${name} ×${count}`].join(' → '),args={item:name};
  if(name==='log')return step('gather','合成依赖：'+reason,{resource:'log'},'dig');
  if(name==='cobblestone')return (!hasPick&&need('wooden_pickaxe',1,[...chain,name]))||step('gather','合成依赖：'+reason,{resource:'stone'},'dig');
  if(name==='planks')return need('log',1,[...chain,name])||step('craft','合成依赖：'+reason,args,'craft');
  const costs={stick:{planks:2},crafting_table:{planks:4},wooden_pickaxe:{planks:3,stick:2},stone_pickaxe:{cobblestone:3,stick:2},stone_axe:{cobblestone:3,stick:2},furnace:{cobblestone:8},torch:{charcoal:1,stick:1}};
  if(name==='charcoal')return need('furnace',1,[...chain,name])||(!m.furnace&&step('station','放置熔炉，准备烧制木炭',{item:'furnace'},'place'))||need('log',1,[...chain,name])||need('planks',2,[...chain,name])||step('smelt','烧制木炭作为火把燃料',{},'smelt');
  if(!costs[name])return step('halt','暂未实现物品：'+name);
  if(!['stick','crafting_table','torch'].includes(name)&&!m.table)return need('crafting_table',1,[...chain,name])||step('station','放置工作台解锁三乘三合成',{item:'crafting_table'},'place');
  for(const [material,n]of Object.entries(costs[name])){const dependency=need(material,n,[...chain,name]);if(dependency)return dependency;}
  return step('craft','合成依赖：'+reason,args,'craft');
 }
 // Placed stations count as owned and are checked against the world by the runner.
 if(!hasPick)return need('wooden_pickaxe');
 if(!inv.stone_pickaxe)return need('stone_pickaxe');
 if(!inv.stone_axe)return need('stone_axe');
 if(!m.furnace)return need('furnace')||step('station','放置熔炉',{item:'furnace'},'place');
 if(!inv.torch&&!m.home)return need('torch',4);
 if(!m.home)return need('planks',30)||step('build','建造带照明的应急庇护所',{},'shelter');
 const meat=['beef','porkchop','mutton','chicken'].find(n=>inv[n]);
 if(meat&&m.furnace)return need('planks',1)||step('smelt','把生肉烤熟，提高食物恢复量',{input:meat},'cook');
 if(foodCount<4)return s.animals.length?step('hunt','建立至少四份食物储备',{entity:s.animals[0].id},'hunt'):step('explore','寻找动物或可食用植物',{resource:'food'},'explore');
 if(goal==='starter')return step('complete','开局目标已确认：石制工具、熔炉、照明庇护所和食物储备',{},'survived');
 if(planks<8)return need('planks',8);
 return step('wait','补给充足，持续监测生命、饥饿、时间与威胁',{},'inspect');
}
module.exports={observe,decide,inventory,FOOD,HOSTILES};
