const $=id=>document.getElementById(id);
const held=new Map(), partValues=new Map();
const samples={tuner:{format:'live2d-tuner/timeline-v1',name:'侧目',duration:1,keyframes:[{t:0,v:{}},{t:.5,v:{ParamAngleX:-15}},{t:1,v:{}}]},dsh:{source:'pose',priority:50,controls:{'head.roll':.4,'gaze.x':-.5}},maibot:{type:'state:emotion',data:{emotion:'happy'}}};
function example(){ $('payload').value=JSON.stringify(samples[$('source').value],null,2); }
example();$('source').onchange=example;
$('file').onchange=async()=>{if($('file').files[0]) $('payload').value=await $('file').files[0].text();};
async function post(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw Error(data.error||r.statusText);return data;}
$('save').onclick=async()=>{try{const {plan}=await post('/api/community/import',{source:$('source').value,payload:JSON.parse($('payload').value)});await post('/api/presets/save',{name:$('name').value,plan});$('status').textContent='已保存，可在主舞台的「我的预设」播放。';}catch(e){$('status').textContent=e.message;}};
function control(parent,label,type,min,max,value,callback){
 const row=document.createElement('label'),field=document.createElement('input');
 field.type=type;field.min=min;field.max=max;field.step=.01;
 if(type==='checkbox')field.checked=!!value;else field.value=value;
 row.append(field,document.createTextNode(' '+label));$(parent).append(row);
 field.oninput=()=>callback(type==='checkbox'?Number(field.checked):Number(field.value));
}
const wear={key10:'大钢盆',key11:'黑框眼镜',key12:'单片眼镜',key7:'脸红',key6:'屑屑眼',key5:'闭眼表情',key4:'爱心眼',key3:'圈圈眼',key2:'落泪',key13:'冷汗',key1:'黑脸',key8:'加载',key9:'大牙',Clothes1:'长短裙',Clothes2:'体型',Clothes3:'胸口衣服',Clothes4:'鞋子',Clothes5:'尾巴'};
try {
 const profile=await (await fetch('/data/model-profile.json')).json();
 const app=new PIXI.Application({view:$('stage'),width:560,height:780,antialias:true,backgroundColor:0xe4ece7});
 const model=await PIXI.live2d.Live2DModel.from('/model/大肥鱼.model3.json',{autoInteract:false,motionPreload:'NONE'});
 model.scale.set(Math.min(540/model.width,750/model.height));model.anchor.set(.5,0);model.position.set(280,10);app.stage.addChild(model);
 const core=model.internalModel.coreModel,parts=core._model.parts,defaults=new Map();
 for(const p of profile.allParameters){
   defaults.set(p.id,p.default);
   const current=core.getParameterValueById(p.id);
   if(Object.hasOwn(wear,p.id)){
     const inverse=p.id==='Clothes4';
     control('wear',wear[p.id],'checkbox',0,1,inverse?current<.5:current>=.5,v=>held.set(p.id,inverse?1-v:v));
   } else if(profile.parameters.some(q=>q.id===p.id)||['Param62','Param60','Param61','Param59','Param36','Param41','Param42','Param39'].includes(p.id)){
     control('sliders',p.name+' · '+p.id,'range',p.min,p.max,current,v=>held.set(p.id,v));
   }
 }
 Array.from(parts.ids).forEach((id,i)=>control('parts',id,'range',0,1,parts.opacities[i],v=>partValues.set(i,v)));
 model.internalModel.on('beforeModelUpdate',()=>{for(const [id,v] of held)core.setParameterValueById(id,v);for(const [i,v] of partValues)parts.opacities[i]=v;});
 let timer,start,frames=[],clip;
 function sample(t){const v=Object.fromEntries([...held].filter(([id,x])=>Math.abs(defaults.get(id)-x)>1e-6));if(!frames.length||t>frames.at(-1).t)frames.push({t,v});}
 function finish(){clearInterval(timer);const duration=Math.min(58,Math.max(.2,(performance.now()-start)/1000));sample(duration);clip={format:'live2d-tuner/timeline-v1',name:$('name').value,duration,keyframes:frames};$('payload').value=JSON.stringify(clip);$('source').value='tuner';$('stop').disabled=true;$('record').disabled=false;$('download').disabled=false;$('status').textContent='已录制 '+frames.length+' 帧';}
 $('record').disabled=false;$('record').onclick=()=>{frames=[];start=performance.now();sample(0);$('record').disabled=true;$('stop').disabled=false;$('status').textContent='正在录制';timer=setInterval(()=>{const t=(performance.now()-start)/1000;if(t>=58)finish();else sample(t);},100);};
 $('stop').onclick=finish;
 $('download').onclick=()=>{const a=document.createElement('a');const url=URL.createObjectURL(new Blob([JSON.stringify(clip,null,2)],{type:'application/json'}));a.href=url;a.download='jingyu-timeline.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
 $('status').textContent='模型就绪';
}catch(e){$('status').textContent=e.message;}
