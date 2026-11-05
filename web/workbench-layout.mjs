// Native details remain keyboard-operable even when saved preferences are unavailable.
for(const section of document.querySelectorAll('details[data-panel]')){
 const key=`jingyu:panel:${section.dataset.panel}`;
 try{const saved=localStorage.getItem(key);if(saved!==null)section.open=saved==='open';}catch{}
 section.addEventListener('toggle',()=>{try{localStorage.setItem(key,section.open?'open':'closed');}catch{}});
}
const menu=document.querySelector('.tools-menu');
document.addEventListener('click',event=>{if(menu&&!menu.contains(event.target))menu.open=false;});
menu?.addEventListener('click',event=>{if(event.target.closest('a,button'))menu.open=false;});
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&menu?.open){menu.open=false;menu.querySelector('summary').focus();}});
