export function bindMinecraft({api,clientId,engine,stage,game,command}){
 const q=id=>document.getElementById(id),marker=q('minecraft-target');let data=null,polling=false;
 async function act(action){
  try{
   q('minecraft-status').textContent='正在执行…';
   if(action!=='shutdown'&&action!=='stop')await command({action:'set',scene:{id:'minecraft',camera:'wide'}});
   await api('/api/minecraft',{action,block:q('minecraft-block').value,clientId,world:q('minecraft-world').value,goal:q('minecraft-goal').value,maxMinutes:Number(q('minecraft-budget').value)});await poll();
  }catch(e){q('minecraft-status').textContent=e.message;}
 }
 for(const b of document.querySelectorAll('[data-minecraft]'))b.onclick=()=>act(b.dataset.minecraft);
 function attention(){
  const a=data?.attention,enabled=stage.classList.contains('game-scene')&&q('minecraft-gaze').checked&&a;
  marker.hidden=!enabled;if(!enabled){engine.attention=null;return;}
  const r=game.getBoundingClientRect(),s=stage.getBoundingClientRect(),g=stage.getTouchGeometry();
  const x=r.left+a.screen.x*r.width,y=r.top+a.screen.y*r.height;
  marker.style.left=(x-s.left)+'px';marker.style.top=(y-s.top)+'px';marker.textContent=(a.screen.visible?'◎ ':'↗ ')+a.label;
  const clamp=v=>Math.max(-1,Math.min(1,v));
  engine.attention={x:clamp((x-(g.x+g.width*.5))/(s.width*.6)),y:clamp(((g.y+g.height*.15)-y)/(s.height*.65)),until:engine.clock+.9};
 }
 async function poll(){
  if(polling)return;polling=true;
  try{
   data=await api('/api/minecraft');
   q('minecraft-status').textContent=!data.running?'本地测试世界未启动':data.error||data.run?.error||(!data.ready?'正在启动 Java 世界…':data.run?.status==='running'?'正在执行 '+data.run.action:data.run?.status==='completed'?'本轮完成':'世界已就绪');
   q('minecraft-inventory').textContent='背包：'+(data.inventory?.map(i=>i.name+' ×'+i.count).join('，')||'—');
   const survival=data.survival;
   q('minecraft-vitals').textContent=data.ready?`${data.mode==='survival'?'普通生存':'试验场'} · 生命 ${data.health??'—'}/20 · 饥饿 ${data.food??'—'}/20 · 时间 ${data.time??'—'}`:'';
   q('minecraft-decision').textContent=survival?.decision?`第 ${survival.step} 步 · ${survival.decision.skill}：${survival.decision.reason}`:'读取环境 → 决定目标 → 执行技能 → 核对结果 → 重新规划';
   q('minecraft-progress').textContent=survival?`状态：${survival.status}${survival.error?' · '+survival.error:''}\n`+(survival.receipts||[]).slice(-3).map(r=>`${r.skill}：${r.status}${r.error?'（'+r.error+'）':''}`).join(' · '):'';
   q('minecraft-narration').textContent=data.narration?.text||'动作发生时显示并解说；声音需先启用。';
   q('minecraft-events').textContent=(data.events||[]).slice(-5).map(e=>new Date(e.at).toLocaleTimeString()+' · '+e.type).join('\n');
   for(const b of document.querySelectorAll('[data-minecraft]')){
    const action=b.dataset.minecraft;b.disabled=action==='start'?data.running:action==='shutdown'?!data.running:action==='stop'?!data.ready:!data.ready||data.run?.status==='running'||(action.startsWith('survival')?data.mode!=='survival':data.mode==='survival');
   }
   if(data.ready&&stage.classList.contains('game-scene')&&game.getAttribute('src')!==data.viewerUrl)game.src=data.viewerUrl;
   attention();
  }catch(e){q('minecraft-status').textContent=e.message;engine.attention=null;}finally{polling=false;}
 }
 q('minecraft-gaze').onchange=attention;
 const timer=setInterval(poll,250);poll();
 window.addEventListener('pagehide',()=>clearInterval(timer));
 stage.getGameAttention=()=>({target:data?.attention,look:engine.attentionLook,input:engine.attention,run:data?.run,narration:data?.narration});
}
