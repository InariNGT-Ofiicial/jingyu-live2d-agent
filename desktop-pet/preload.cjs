const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('jingyuPet',{
 ready:()=>ipcRenderer.send('pet:ready'),
 error:message=>ipcRenderer.send('pet:error',String(message)),
 telemetry:value=>ipcRenderer.send('pet:telemetry',value),
 onPointer:callback=>{const listener=(_,point)=>callback(point);ipcRenderer.on('pet:pointer',listener);return ()=>ipcRenderer.removeListener('pet:pointer',listener);},
 control:action=>{if(['close','larger','smaller','click-through'].includes(action))ipcRenderer.send('pet:control',action);}
});
