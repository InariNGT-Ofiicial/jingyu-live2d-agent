const $=id=>document.getElementById(id);
let candidate,removing,busy=false;
async function api(path,data){const r=await fetch(path,{method:data===undefined?'GET':'POST',headers:data===undefined?{}:{'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data)});const v=await r.json();if(!r.ok)throw Error(v.error||'请求失败');return v;}
export function savePresetDialog(plan){
  if(!plan)return;candidate=structuredClone(plan);$('preset-name').value=plan.title||'';
  $('preset-save-status').textContent='保存计划中的动作、节奏与幅度；播放时使用当前选择的后端。';
  $('preset-save-dialog').showModal();$('preset-name').focus();
}
export async function refreshPresets(){
  try{
    const {presets}=await api('/api/presets');const list=$('user-preset-list');list.replaceChildren();
    $('user-preset-count').textContent=presets.length+' 个';
    if(!presets.length){const p=document.createElement('p');p.className='muted';p.textContent='把喜欢的编排保存下来，下次直接播放。';list.append(p);}
    for(const p of presets){
      const row=document.createElement('div');row.className='user-preset-row';
      const play=document.createElement('button');play.className='demo-button';play.type='button';
      const text=document.createElement('span'),name=document.createElement('strong'),detail=document.createElement('small');
      name.textContent=p.name;detail.textContent=p.duration.toFixed(1)+' 秒 · 点击播放';text.append(name,detail);play.append(text);
      play.onclick=async()=>{play.disabled=true;try{await api('/api/presets/play',{id:p.id,backend:$('backend-select').value});$('preset-list-status').textContent='正在播放：'+p.name;}catch(e){$('preset-list-status').textContent=e.message;}finally{play.disabled=false;}};
      const del=document.createElement('button');del.type='button';del.className='small-button preset-delete';del.textContent='删除';del.setAttribute('aria-label','删除预设 '+p.name);
      del.onclick=()=>{removing=p;$('preset-delete-name').textContent='删除“'+p.name+'”？此操作无法撤销。';$('preset-delete-status').textContent='';$('preset-delete-dialog').showModal();};
      row.append(play,del);list.append(row);
    }
  }catch(e){$('preset-list-status').textContent=e.message;}
}
$('preset-save-form').onsubmit=async e=>{e.preventDefault();if(busy)return;busy=true;$('preset-save-submit').disabled=true;
  try{const p=await api('/api/presets/save',{name:$('preset-name').value,plan:candidate});$('preset-save-dialog').close();$('preset-list-status').textContent='已保存：'+p.name;await refreshPresets();}
  catch(e){$('preset-save-status').textContent=e.message;}finally{busy=false;$('preset-save-submit').disabled=false;}
};
$('preset-save-cancel').onclick=()=>$('preset-save-dialog').close();
$('preset-delete-cancel').onclick=()=>$('preset-delete-dialog').close();
$('preset-delete-confirm').onclick=async()=>{if(busy||!removing)return;busy=true;$('preset-delete-confirm').disabled=true;
  try{const result=await api('/api/presets/delete',{id:removing.id});$('preset-delete-dialog').close();$('preset-list-status').textContent='已删除：'+result.name;await refreshPresets();}
  catch(e){$('preset-delete-status').textContent=e.message;}finally{busy=false;$('preset-delete-confirm').disabled=false;}
};
$('refresh-presets').onclick=refreshPresets;
await refreshPresets();
