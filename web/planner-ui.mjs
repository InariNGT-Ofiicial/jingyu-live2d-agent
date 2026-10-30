import {savePresetDialog} from './presets-ui.mjs';
const $=id=>document.getElementById(id);
let selected, active, config;
const labels={queued:'等待模型',generating:'模型正在编排…',repairing:'正在修正校验问题…',validated:'计划已通过本地校验',executed:'已送入执行后端',error:'编排失败',cancelled:'已取消采纳结果；已发送的服务请求可能仍在结束中'};
async function api(path,data){const r=await fetch(path,{method:data===undefined?'GET':'POST',headers:data===undefined?{}:{'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data)});const v=await r.json();if(!r.ok)throw Error(v.error||'请求失败');return v;}
function status(text,error=false){$('planner-status').textContent=text;$('planner-status').classList.toggle('error',error);}
function renderTask(t){
 active=t?.id||active;if(!t)return;
 status((labels[t.status]||t.status)+(t.error?' · '+t.error:''),t.status==='error');
 const busy=t.running===true;
 $('generate-plan').disabled=busy;$('generate-plan').textContent=busy?'正在编排…':'生成动作计划';
 $('play-plan').disabled=!['validated','executed'].includes(t.status);
 $('play-plan').textContent=t.status==='executed'?'重新播放此计划 ↻':'播放已校验计划 ▷';
 $('save-planner-preset').disabled=!['validated','executed'].includes(t.status);
 $('cancel-plan').disabled=!['queued','generating','repairing','validated'].includes(t.status);
 if(t.plan){selected=t;$('planner-plan').hidden=false;$('planner-title').textContent=t.plan.title||'动作计划';
  $('planner-summary').textContent=t.plan.summary||t.plan.intent||'';
  $('planner-source').textContent=t.planner.model+' · '+(t.backend==='vts'?'VTS':'网页')+' · '+t.compiled.duration.toFixed(1)+' 秒 · '+t.compiled.steps.length+' 个动作';
  $('planner-json').textContent=JSON.stringify(t.plan,null,2);
 }
}
function renderConfig(c){
 config=c;$('planner-provider').value=c.provider;$('planner-protocol').value=c.protocol;
 $('planner-url').value=c.baseUrl;$('planner-model').value=c.model;$('planner-json-mode').checked=c.jsonMode;
 $('planner-key').value='';$('planner-key').placeholder=c.hasApiKey?'已保存在本次服务内存；留空保持':'可留空用于本地免密服务';
 $('provider-current').textContent=c.provider==='dsh'?'本机 DSH':c.model||'配置模型接口';
 $('api-settings').hidden=c.provider==='dsh';$('dsh-settings').hidden=c.provider!=='dsh';
}
async function refresh(){try{const s=await api('/api/planner/state');if(!config)renderConfig(s.config);const t=s.tasks.find(x=>x.id===active)||s.tasks[0];if(t)renderTask(t);}catch(e){status(e.message,true);}}
$('open-model-settings').onclick=async()=>{try{renderConfig(await api('/api/planner/config'));$('model-settings').showModal();}catch(e){status(e.message,true);}};
$('close-model-settings').onclick=()=>$('model-settings').close();
$('planner-provider').onchange=()=>{const d=$('planner-provider').value==='dsh';$('api-settings').hidden=d;$('dsh-settings').hidden=!d;};
$('model-settings-form').onsubmit=async e=>{
 e.preventDefault();$('save-model-settings').disabled=true;
 try{const c={provider:$('planner-provider').value,protocol:$('planner-protocol').value,baseUrl:$('planner-url').value.trim(),model:$('planner-model').value.trim(),jsonMode:$('planner-json-mode').checked};
  if($('planner-key').value)c.apiKey=$('planner-key').value;
  if($('planner-clear-key').checked)c.apiKey='';
  renderConfig(await api('/api/planner/config',c));$('planner-clear-key').checked=false;$('model-settings').close();status('编排来源已配置，可输入情境生成计划。');
 }catch(e){$('settings-feedback').textContent=e.message;}finally{$('save-model-settings').disabled=false;}
};
$('llm-prompt-form').onsubmit=async e=>{
 e.preventDefault();const prompt=$('llm-prompt').value.trim();if(!prompt)return;
 $('generate-plan').disabled=true;selected=null;$('play-plan').disabled=true;$('planner-plan').hidden=true;
 try{const t=await api('/api/planner/run',{prompt,backend:$('backend-select').value});active=t.id;renderTask(t);}catch(e){status(e.message,true);$('generate-plan').disabled=false;}
};
$('play-plan').onclick=async()=>{
 if(!selected)return;$('play-plan').disabled=true;
 try{const replay=selected.status==='executed';const job=await api(replay?'/api/planner/replay':'/api/planner/execute',{taskId:selected.id,...(replay?{backend:$('backend-select').value}:{})});selected.status='executed';selected.jobId=job.id;status('舞台正在执行 · 等待 completed 回执');active=selected.id;
  const label=$('source-badge');if(label)label.textContent=job.source;
 }catch(e){status(e.message,true);}
};
$('save-planner-preset').onclick=()=>{if(selected)savePresetDialog(selected.plan);};
$('cancel-plan').onclick=async()=>{if(active)try{renderTask(await api('/api/planner/cancel',{taskId:active}));}catch(e){status(e.message,true);}};
let polling=false;
setInterval(async()=>{if(polling)return;polling=true;try{await refresh();const s=await api('/api/state');if(s.activeJob&&['queued','compiling','deploying','playing','stopping'].includes(s.activeJob.status))$('play-plan').disabled=true;if(selected?.jobId){const j=s.jobs.find(x=>x.id===selected.jobId);if(j&&['completed','error','interrupted'].includes(j.status))status(j.status==='completed'?'表演已完成 · '+(j.backend==='vts'?'VTS':'网页'):`舞台状态：${j.status}`,j.status==='error');}}catch(e){status(e.message,true);}finally{polling=false;}},1200);
await refresh();
