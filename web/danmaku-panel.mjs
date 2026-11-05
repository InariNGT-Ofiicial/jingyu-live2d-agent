export function bindDanmaku({api,clientId,audioInit,stop,play}){
 const $=id=>document.getElementById(id),seen=new Set();
 const labels={queued:'等待回复',claimed:'Agent 正在回复',replying:'正在合成',playing:'正在说话',done:'已回复',error:'失败',cancelled:'已停止',skipped:'队列已满'};
 let state={running:false,messages:[]};
 function update(value){
  state=value;
  $('danmaku-start').disabled=value.running;$('danmaku-stop').disabled=!value.running;
  $('danmaku-send').disabled=!value.running;
  $('danmaku-status').textContent=value.running?(value.producing?'随机弹幕运行中':'定时发送已结束')+' · 排队 '+value.queued+' 条 · 回复来源：外部 Agent':'测试已停止 · 仅使用模拟弹幕';
  const rows=value.messages.slice(-12).reverse().map(m=>{
   const li=document.createElement('li'),title=document.createElement('strong'),body=document.createElement('p'),status=document.createElement('small');
   title.textContent=m.author+' · '+(m.source==='timer'?'定时模拟':'手动测试');body.textContent=m.text;
   status.textContent=labels[m.status]||m.status;li.append(title,body,status);
   if(m.reply){const answer=document.createElement('p');answer.className='danmaku-answer';answer.textContent='DS 娘：'+m.reply;li.append(answer);}
   if(m.error){const error=document.createElement('small');error.textContent=m.error;li.append(error);}
   return li;
  });
  $('danmaku-list').replaceChildren(...rows);
  const current=value.messages.find(m=>m.id===value.activeId),latest=current||value.messages.at(-1);
  $('danmaku-bubble').textContent=latest&&value.running?(current?'正在回复 · ':'模拟弹幕 · ')+latest.author+'：'+latest.text:'';
 }
 function fail(e){$('danmaku-status').textContent=e.message;}
 $('danmaku-start').onclick=async()=>{
  try{await audioInit();await api('/api/studio/voice/warmup',{});update(await api('/api/studio/danmaku/start',{clientId,
   minInterval:Number($('danmaku-min').value),maxInterval:Number($('danmaku-max').value),count:Number($('danmaku-count').value)}));}catch(e){fail(e);}
 };
 $('danmaku-stop').onclick=async()=>{stop();try{update(await api('/api/studio/danmaku/stop',{}));}catch(e){fail(e);}};
 $('danmaku-send').onclick=async()=>{try{await api('/api/studio/danmaku/message',{author:'测试观众',text:$('danmaku-text').value});$('danmaku-text').value='';}catch(e){fail(e);}};
 api('/api/studio/danmaku').then(update).catch(fail);
 return {update,async receive(packet){
  if(packet.clientId!==clientId||seen.has(packet.messageId))return;
  seen.add(packet.messageId);if(seen.size>100)seen.delete(seen.values().next().value);
  try{await play(packet.job,packet.messageId);}catch(e){fail(e);}
 }};
}
