// Fetch each short clip once. Two native video surfaces let the compositor keep
// the outgoing frame visible while the other decoder presents its first frame.
export function mobileMotion(figure,policy,director,onError){
 const log=window.motionLog=[],cache=new Map(),failed=new Set(),controller=new AbortController();
 const stats=window.motionStats={downloads:[],assetWaitMs:0,cutMaxMs:0,shown:0,dropped:0,total:0,frameGapMs:0,playedMs:0};
 const names=Object.keys(policy.clips);
 const starterNames=['front-breathe','h3-shoulders'],upgrade=[...starterNames],urls=[];
 const queue=[...new Set(['front-breathe','h3-shoulders','h3-ribbon','listen',...names])];
 let closed=false,loading=null,active=null,visible=null,waiting=null,first=true,callback=0;
 const surfaces=[0,1].map(()=>{
  const v=document.createElement('video');v.className='motionSurface';v.muted=true;v.playsInline=true;
  v.setAttribute('aria-hidden','true');v.preload='auto';figure.append(v);return v;
 });
 const started=performance.now();
 let visibleSince=started;
 function visibility(){visibleSince=performance.now();stats.lastFrame=null}
 document.addEventListener('visibilitychange',visibility);
 function prepare(v,name){
  if(v.src!==cache.get(name)){v.dataset.clip=name;v.src=cache.get(name);v.load()}
 }
 function warm(name){
  if(!names.includes(name)||cache.has(name)||failed.has(name)||loading===name)return;
  const index=queue.indexOf(name);if(index>=0)queue.splice(index,1);
  const starterCount=queue.filter(n=>starterNames.includes(n)).length;
  queue.splice(starterNames.includes(name)?0:starterCount,0,name);
 }
 function prime(){
  if(!active||visible!==active.video)return;
  const state=director.state||'idle';
  const choices=[director.pending?.name,...(policy.pools[state]||[]),...policy.pools.idle];
  const next=choices.find(n=>n!==active.name&&cache.has(n));
  if(next)prepare(surfaces.find(v=>v!==visible),next);
 }
 async function load(){
  if(closed||(!queue.length&&!upgrade.length))return;
  const name=loading=queue.length?queue.shift():upgrade.shift(),begin=performance.now();
  const starter=starterNames.includes(name)&&!cache.has(name);
  try{
   let r=await fetch('/motions/'+policy.mobileDirectory+'/'+name+(starter?'-start':'')+'.mp4',{signal:controller.signal});
   if(!r.ok)r=await fetch('/motions/'+policy.clips[name].file,{signal:controller.signal});
   if(!r.ok)throw Error('动作下载失败');
   const blob=await r.blob();if(closed)return;
   const url=URL.createObjectURL(blob);urls.push(url);cache.set(name,url);stats.downloads.push({name,starter,ms:Math.round(performance.now()-begin),bytes:blob.size});
  }catch{if(closed)return;if(!cache.has(name))failed.add(name)}
  loading=null;
  if(!active)advance();else prime();
  if(!closed)void load();
 }
 function advance(){
  if(closed||active)return;
  const choice=director.next(n=>cache.has(n)&&!failed.has(n));
  if(!choice){
   if(waiting===null)waiting=performance.now();
   if(failed.size===names.length)onError('动作资源未能加载');
   return;
  }
  if(waiting!==null){if(!first)stats.assetWaitMs+=performance.now()-waiting;waiting=null}
  const v=surfaces.find(el=>el!==visible),entry={...choice,start:performance.now(),turnIds:choice.turnId==null?[]:[choice.turnId]};
  active={name:choice.name,video:v};log.push(entry);if(log.length>400)log.shift();
  prepare(v,choice.name);v.currentTime=0;
  const quality=()=>v.getVideoPlaybackQuality?.();
  let prev=null,base=null;
  function paint(now,meta){
   if(closed||active?.video!==v)return;
   if(!entry.firstFrame){
    entry.firstFrame=now;
    if(first){stats.startupMs=now-started;first=false}
    else if(!document.hidden && stats.lastFrame)stats.cutMaxMs=Math.max(stats.cutMaxMs,now-stats.lastFrame);
    if(visible)visible.classList.remove('current');
    v.classList.add('current');visible=v;base=quality();prime();
   }
   if(!document.hidden){
    if(prev!==null&&prev>=visibleSince){stats.frameGapMs=Math.max(stats.frameGapMs,now-prev);stats.playedMs+=now-prev;stats.shown++}
    prev=now;stats.lastFrame=now;
   }else{prev=null;stats.lastFrame=null}
   entry.lastMediaTime=meta.mediaTime;callback=v.requestVideoFrameCallback(paint);
  }
  function finish(error){
   if(closed||active?.video!==v)return;
   const q=quality();
   if(q&&base){stats.dropped+=Math.max(0,q.droppedVideoFrames-base.droppedVideoFrames);stats.total+=Math.max(0,q.totalVideoFrames-base.totalVideoFrames)}
   v.cancelVideoFrameCallback(callback);v.pause();v.onended=null;v.onerror=null;
   entry.end=performance.now();entry.lastTime=v.currentTime;entry.duration=v.duration;entry.recovery=Boolean(error);
   if(error)failed.add(choice.name);
   active=null;advance();
  }
  callback=v.requestVideoFrameCallback(paint);v.onended=()=>finish(false);v.onerror=()=>finish(true);
  v.play().catch(()=>finish(true));
 }
 function request(name,turnId,since,options){
  warm(name);
  const shown=log.findLast(e=>e.name===name&&!failed.has(name)&&(e.end?e.end>since:active?.name===name));
  if(shown&&!shown.turnIds.includes(turnId))shown.turnIds.push(turnId);
  director.request(name,{...options,turnId,covered:Boolean(shown)});prime();
 }
 void load();
 return {director,warm,request,close(){
  closed=true;controller.abort();document.removeEventListener('visibilitychange',visibility);
  for(const v of surfaces){v.cancelVideoFrameCallback(callback);v.pause();v.removeAttribute('src');v.load();v.remove()}
  for(const url of urls)URL.revokeObjectURL(url);
 }};
}
