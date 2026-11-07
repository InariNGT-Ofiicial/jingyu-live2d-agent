const {app,BrowserWindow,ipcMain,screen,Tray,Menu,nativeImage}=require('electron');
const fs=require('node:fs'),path=require('node:path');
const args=process.argv.slice(1);
const arg=(name,fallback)=>{const i=args.indexOf(name);return i<0?fallback:args[i+1];};
const base=new URL(arg('--url','http://127.0.0.1:61944'));
if(base.protocol!=='http:'||base.hostname!=='127.0.0.1'||!base.port)throw Error('桌宠只连接本机工作台');
const port=base.port,root=path.resolve(__dirname,'..');
const folder=path.join(root,'.local','web-pet');fs.mkdirSync(folder,{recursive:true});
const statePath=path.join(folder,port+'.json');
app.setPath('userData',path.join(folder,'profile-'+port));
app.commandLine.appendSwitch('disable-renderer-backgrounding');
app.commandLine.appendSwitch('disable-backgrounding-occluded-windows');
// Keep the 715-mesh model off the power-saving adapter on dual-GPU laptops.
if(process.env.JINGYU_PET_GPU!=='default')app.commandLine.appendSwitch('force_high_performance_gpu');
if(/^\d{4,5}$/.test(process.env.JINGYU_PET_DEBUG_PORT||'')){
 app.commandLine.appendSwitch('remote-debugging-port',process.env.JINGYU_PET_DEBUG_PORT);
 app.commandLine.appendSwitch('remote-debugging-address','127.0.0.1');
}
let win,tray,timer,pointerTimer,ready=false,passThrough=false,lastTelemetry={},lastFrameAt=0;
const title=`鲸语 · 网页桌宠 · ${port}`;
function state(error){
 const value={renderer:'web',pid:process.pid,port:Number(port),ready,running:!!win&&!win.isDestroyed(),
  transparent:true,clickThrough:passThrough,lastFrameAt,telemetry:lastTelemetry,gpu:app.isReady()?app.getGPUFeatureStatus():{},updatedAt:Date.now(),...(error?{error}:{}),
  bounds:win&&!win.isDestroyed()?win.getBounds():null};
 fs.writeFileSync(statePath,JSON.stringify(value));
}
function failure(error){console.error(String(error));ready=false;state(String(error));app.exit(1);}
function resize(factor){
 const area=screen.getDisplayMatching(win.getBounds()).workArea,b=win.getBounds();
 const h=Math.max(300,Math.min(area.height,Math.round(b.height*factor))),w=Math.round(h*480/700);
 win.setBounds({width:w,height:h,x:Math.max(area.x,Math.min(b.x+b.width-w,area.x+area.width-w)),y:Math.max(area.y,Math.min(b.y+b.height-h,area.y+area.height-h))});
}
function interaction(value){passThrough=value;win.setIgnoreMouseEvents(value,{forward:true});refreshMenu();state();}
function showPet(){win.showInactive();win.setAlwaysOnTop(true,'screen-saver');win.moveTop();}
function refreshMenu(){tray?.setContextMenu(Menu.buildFromTemplate([
 {label:'鲸语 · 网页桌宠（无需 VTS）',enabled:false},
 {label:'鼠标穿透',type:'checkbox',checked:passThrough,click:item=>interaction(item.checked)},
 {label:'恢复交互',click:()=>{interaction(false);showPet();}},
 {type:'separator'},{label:'放大',click:()=>resize(1.1)},{label:'缩小',click:()=>resize(1/1.1)},
 {type:'separator'},{label:'退出桌宠',click:()=>app.quit()}
 ]));}
function trusted(event){return win&&event.sender===win.webContents&&event.senderFrame?.url.startsWith(base.origin+'/pet.html');}
ipcMain.on('pet:ready',(event)=>{if(!trusted(event))return;ready=true;showPet();state();});
ipcMain.on('pet:error',(event,message)=>{if(trusted(event))failure(message);});
ipcMain.on('pet:telemetry',(event,value)=>{if(trusted(event)){lastTelemetry=value;lastFrameAt=Date.now();state();}});
ipcMain.on('pet:control',(event,action)=>{
 if(!trusted(event))return;
 if(action==='close')app.quit();
 else if(action==='larger')resize(1.1);
 else if(action==='smaller')resize(1/1.1);
 else if(action==='click-through')interaction(true);
});
app.whenReady().then(async()=>{
 const area=screen.getPrimaryDisplay().workArea,h=Math.min(700,area.height-30),w=Math.round(h*480/700);
 win=new BrowserWindow({title,width:w,height:h,x:area.x+area.width-w-20,y:area.y+area.height-h,
  transparent:true,backgroundColor:'#00000000',frame:false,resizable:false,hasShadow:false,
  alwaysOnTop:true,skipTaskbar:true,show:false,
  webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,sandbox:true,
   nodeIntegration:false,backgroundThrottling:false,spellcheck:false}});
 win.on('page-title-updated',event=>event.preventDefault());
 win.webContents.setWindowOpenHandler(()=>({action:'deny'}));
 win.webContents.on('will-navigate',(event,url)=>{if(new URL(url).origin!==base.origin)event.preventDefault();});
 win.webContents.on('render-process-gone',(_,details)=>failure('网页渲染器退出：'+details.reason));
 win.webContents.on('did-fail-load',(_,code,description)=>failure(`网页加载失败 ${code}: ${description}`));
 const pixels=Buffer.alloc(16*16*4);
 for(let y=0;y<16;y++)for(let x=0;x<16;x++)if((x-7.5)**2+(y-7.5)**2<54){const i=(y*16+x)*4;pixels[i]=86;pixels[i+1]=122;pixels[i+2]=53;pixels[i+3]=255;if(y===6&&(x===5||x===10))pixels.fill(255,i,i+4);}
 tray=new Tray(nativeImage.createFromBitmap(pixels,{width:16,height:16}));tray.setToolTip('鲸语网页桌宠 · 右键管理');
 tray.on('double-click',()=>{interaction(false);showPet();});refreshMenu();
 timer=setInterval(state,2000);state();
 pointerTimer=setInterval(()=>{
  if(!ready||!win||win.isDestroyed())return;
  const point=screen.getCursorScreenPoint(),bounds=win.getContentBounds();
  win.webContents.send('pet:pointer',{x:point.x,y:point.y,window:bounds,desktop:screen.getDisplayMatching(bounds).workArea,clickThrough:passThrough});
 },40);
 await win.loadURL(base.origin+'/pet.html?desktop=1');
 setTimeout(()=>{if(!ready)failure('模型未在 40 秒内加载完成，请检查工作台和模型资源');},40000).unref();
}).catch(failure);
app.on('window-all-closed',()=>app.quit());
app.on('before-quit',()=>{clearInterval(timer);clearInterval(pointerTimer);ready=false;state();});
app.on('will-quit',()=>{tray?.destroy();try{fs.unlinkSync(statePath);}catch{}});
