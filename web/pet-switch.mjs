const button=document.querySelector('#pet-switch'), note=document.querySelector('#pet-status');
let busy=false, revision=0;
function show(s){
  button.setAttribute('aria-checked',String(s.running));
  button.textContent=s.running?'关闭网页桌宠':'开启网页桌宠';
  button.disabled=!s.available;
  if(!s.available) note.textContent=s.error||'网页桌宠需要 Windows';
}
async function refresh(){
  if(busy)return;
  const token=++revision;
  try{
    const response=await fetch('/api/pet');
    if(!response.ok)throw Error();
    const state=await response.json();
    if(token===revision){show(state);if(note.dataset.offline){note.textContent='';delete note.dataset.offline;}}
  }catch{if(token===revision){button.disabled=true;note.textContent='无法连接工作台';note.dataset.offline='1';}}
}
button.onclick=async()=>{
  busy=true;++revision;button.disabled=true;
  const enabled=button.getAttribute('aria-checked')!=='true';
  note.textContent=enabled?'正在载入网页模型…':'正在关闭…';
  try{
    const r=await fetch('/api/pet',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled})});
    const s=await r.json();if(!r.ok)throw Error(s.error);
    show(s);note.textContent='';
  }catch(e){note.textContent=e.message;}
  finally{busy=false;refresh();}
};
refresh();setInterval(()=>{if(!document.hidden)refresh();},3000);
window.addEventListener('focus',refresh);
