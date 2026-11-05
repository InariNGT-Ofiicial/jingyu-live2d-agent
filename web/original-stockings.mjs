export function garmentOpacity(progress){const t=Math.max(0,Math.min(1,(progress-.92)/.08));return 1-t*t*(3-2*t);}
export function strapOpacity(progress){const t=Math.max(0,Math.min(1,(progress-.02)/.26));return 1-t*t*(3-2*t);}
// Interpolate along the original UV mesh, including its current authored deformation.
export function meshAnchor(vertices,uv,indices,y){
 const hits=[];
 for(let k=0;k<indices.length;k+=3)for(let j=0;j<3;j++){
  const a=indices[k+j]*2,b=indices[k+(j+1)%3]*2,ay=1-uv[a+1],by=1-uv[b+1];
  if(Math.abs(by-ay)<1e-8||y<Math.min(ay,by)||y>Math.max(ay,by))continue;
  const t=(y-ay)/(by-ay);hits.push({x:vertices[a]+t*(vertices[b]-vertices[a]),y:vertices[a+1]+t*(vertices[b+1]-vertices[a+1])});
 }
 if(!hits.length)return null;
 hits.sort((a,b)=>a.x-b.x);const a=hits[0],b=hits[hits.length-1];return {x:(a.x+b.x)/2,y:(a.y+b.y)/2,width:b.x-a.x};
}
// Shared clothing interaction. Original textures, mesh topology, UVs and masks stay unchanged.
export function installStockingShader(gl){
 let progress=-1,skinTexture=null;const locations=new WeakMap(),source=gl.shaderSource.bind(gl),draw=gl.drawElements.bind(gl),use=gl.useProgram.bind(gl);let currentProgram=null;
 gl.useProgram=program=>{currentProgram=program;use(program);};
 const code=`uniform float jyStockingProgress;
 uniform sampler2D jySkinTexture;uniform float jySkinReady;
 vec4 jyStocking(vec4 c,vec2 uv){
  if(jyStockingProgress<=0.0)return c;
  float edge=jyStockingProgress>=0.995?0.49:mix(0.296,0.476,jyStockingProgress);
  float reveal=smoothstep(0.288,0.294,uv.y)*(1.0-smoothstep(edge-0.001,edge+0.001,uv.y));
  vec4 sampleSkin=texture2D(s_texture0,vec2(0.621,0.274));
  vec3 skin=sampleSkin.rgb/max(sampleSkin.a,0.001);
  vec3 original=c.rgb/max(c.a,0.001);
  float light=dot(original,vec3(0.299,0.587,0.114));
  vec3 bare=skin*clamp(light/0.94,0.72,1.06);
  if(jySkinReady>0.5){
   vec2 patch=clamp((uv-vec2(2385.0/4096.0,1690.0/8192.0))/vec2(345.0/4096.0,2220.0/8192.0),0.0,1.0);
   vec2 paintedUV=(vec2(237.0,80.0)+patch*vec2(293.0,1887.0))/vec2(768.0,2048.0);
   vec3 painted=texture2D(jySkinTexture,paintedUV).rgb;
   vec3 anchorColor=texture2D(jySkinTexture,(vec2(237.0,80.0)+vec2(0.5,0.26)*vec2(293.0,1887.0))/vec2(768.0,2048.0)).rgb;
   painted*=skin/max(anchorColor,vec3(0.01));
   if(painted.r-painted.b>0.018)bare=mix(bare,painted,0.98);
  }
  c.rgb=mix(c.rgb,bare*c.a,reveal);
  float fold=smoothstep(edge-0.001,edge,uv.y)*(1.0-smoothstep(edge+0.004,edge+0.012,uv.y));
  if(jyStockingProgress<0.99)c.rgb*=1.0-fold*(0.09+0.07*sin((uv.y-edge)*2600.0));
  return c;
 }
 `;
 gl.shaderSource=(shader,text)=>{
  if(text.includes('vec4 bridgeColor(vec2 uv)'))text=text.replace('vec4 bridgeColor(vec2 uv)',code+'vec4 bridgeColor(vec2 uv)').replace('vec4 c=texture2D(s_texture0,uv);','vec4 c=jyStocking(texture2D(s_texture0,uv),uv);');
  source(shader,text);
 };
 gl.drawElements=(...args)=>{
  const program=currentProgram;let previousUnit,previousTexture;
  if(program){
   if(!locations.has(program))locations.set(program,{progress:gl.getUniformLocation(program,'jyStockingProgress'),skin:gl.getUniformLocation(program,'jySkinTexture'),ready:gl.getUniformLocation(program,'jySkinReady')});
   const loc=locations.get(program);if(loc.progress!==null)gl.uniform1f(loc.progress,progress);
   if(loc.ready!==null)gl.uniform1f(loc.ready,skinTexture?1:0);
   if(loc.skin!==null){
    gl.uniform1i(loc.skin,skinTexture&&progress>0?2:0);
    if(skinTexture&&progress>0){previousUnit=gl.getParameter(gl.ACTIVE_TEXTURE);gl.activeTexture(gl.TEXTURE2);previousTexture=gl.getParameter(gl.TEXTURE_BINDING_2D);gl.bindTexture(gl.TEXTURE_2D,skinTexture);}
   }
  }
  try{draw(...args);}finally{if(previousUnit!==undefined){gl.bindTexture(gl.TEXTURE_2D,previousTexture);gl.activeTexture(previousUnit);}}
 };
 const set=value=>{progress=value;};set.skinReady=false;
 if(typeof Image!=='undefined'){
  const image=new Image();image.onload=()=>{
   const active=gl.getParameter(gl.ACTIVE_TEXTURE);gl.activeTexture(gl.TEXTURE2);const previous=gl.getParameter(gl.TEXTURE_BINDING_2D),flip=gl.getParameter(gl.UNPACK_FLIP_Y_WEBGL),premultiply=gl.getParameter(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL);
   try{skinTexture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,skinTexture);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,false);gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL,false);
    gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,image);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);set.skinReady=true;
   }finally{gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,flip);gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL,premultiply);gl.bindTexture(gl.TEXTURE_2D,previous);gl.activeTexture(active);}
  };image.src='/assets/stocking-study/skin-gloss-anime-v6.png';
 }
 return set;
}
export const STOCKINGS_ENABLED_KEY='jingyu:clothing:stockings-enabled';
export function stockingsEnabled(storage){try{return storage.getItem(STOCKINGS_ENABLED_KEY)!=='false';}catch{return true;}}
export function bindOriginalStockings({model,stage,canvas,renderer,setShaderProgress,busy,occluded=()=>false}){
 const internal=model.internalModel,core=internal.coreModel;
 const legs=['ArtMesh584','ArtMesh653'].map(id=>({id,index:core.getDrawableIndex(id),progress:0}));
 if(legs.some(l=>l.index<0))return;
 let enabled=true,drag=null;
 try{enabled=stockingsEnabled(localStorage);}catch{}
 const laceIds=[['ArtMesh579','ArtMesh569','ArtMesh568','ArtMesh567','ArtMesh566','ArtMesh565','ArtMesh564','ArtMesh563','ArtMesh562','ArtMesh561','ArtMesh560','ArtMesh559'],['ArtMesh640','ArtMesh637','ArtMesh636','ArtMesh635','ArtMesh634','ArtMesh577','ArtMesh576','ArtMesh575','ArtMesh574','ArtMesh573','ArtMesh572','ArtMesh571']];
 const nativeModelDraw=internal.renderer.doDrawModel;
 internal.renderer.doDrawModel=function(...args){
  const restore=[];
  if(enabled)legs.forEach((leg,n)=>{
   if(leg.progress<=0)return;
   const v=core.getDrawableVertices(leg.index),uv=core.getDrawableVertexUvs(leg.index),indices=core.getDrawableVertexIndices(leg.index);
   const from=meshAnchor(v,uv,indices,.296),to=meshAnchor(v,uv,indices,.296+.178*leg.progress);
   if(!from||!to)return;
   const scale=Math.max(.45,Math.min(1.25,to.width/Math.max(.001,from.width)));
   for(const id of laceIds[n]){const index=core.getDrawableIndex(id);if(index<0)continue;
    const points=core.getDrawableVertices(index);restore.push([points,points.slice()]);
    for(let i=0;i<points.length;i+=2){points[i]=to.x+(points[i]-from.x)*scale;points[i+1]+=to.y-from.y;}
   }
  });
  try{return nativeModelDraw.apply(this,args);}finally{for(const [points,original] of restore)points.set(original);}
 };

 const straps=[['ArtMesh578','ArtMesh570'],['ArtMesh639','ArtMesh638']].map(ids=>ids.map(id=>core.getDrawableIndex(id)));
 const removable=[['ArtMesh633','ArtMesh632','ArtMesh583','ArtMesh582','ArtMesh581','ArtMesh580',...laceIds[0]],['ArtMesh655','ArtMesh654','ArtMesh644','ArtMesh643','ArtMesh642','ArtMesh641',...laceIds[1]]].map(ids=>ids.map(id=>core.getDrawableIndex(id)));
 const nativeDraw=internal.renderer.drawMesh;
 internal.renderer.drawMesh=function(...args){
  const leg=legs.find(l=>core.getDrawableVertexUvs(l.index)===args[5]);
  if(enabled)straps.forEach((ids,n)=>{if(ids.some(i=>i>=0&&core.getDrawableVertexUvs(i)===args[5]))args[6]*=strapOpacity(legs[n].progress);});
  if(enabled)removable.forEach((ids,n)=>{if(ids.some(i=>i>=0&&core.getDrawableVertexUvs(i)===args[5]))args[6]*=garmentOpacity(legs[n].progress);});
  setShaderProgress(enabled&&leg&&!this.getClippingContextBufferForMask()?leg.progress:-1);
  try{return nativeDraw.apply(this,args);}finally{setShaderProgress(-1);}
 };
 const panel=document.createElement('section');panel.id='stocking-controls';panel.style.cssText='padding:12px 0;color:inherit;font-size:14px;line-height:1.8';
 panel.innerHTML='<label><input id="original-stockings-toggle" type="checkbox"> 服装交互 · 丝袜拖拽</label> <button id="stockings-reset" type="button">恢复原袜</button><div>在全身视图抓住蕾丝袜口向下拖，松手保留位置；拖到底时该侧丝袜与鞋一起隐藏。点击「恢复原袜」可重置，关闭开关显示原始服装。</div><output id="stockings-status">已关闭 · 原始服装</output>';
 const host=document.getElementById('stocking-controls-host');
 if(host)host.replaceChildren(panel);else stage.after(panel);
 const output=panel.querySelector('output');
 const status=()=>{output.textContent=enabled?'两腿下拉进度：'+legs.map(l=>Math.round(l.progress*100)+'%').join(' / '):'已关闭 · 原始服装';};
 const end=()=>{if(drag&&stage.hasPointerCapture(drag.pointer))stage.releasePointerCapture(drag.pointer);drag=null;};
 const toggle=panel.querySelector('input');
 const applyEnabled=value=>{enabled=value;toggle.checked=value;end();status();};
 toggle.onchange=e=>{applyEnabled(e.target.checked);try{localStorage.setItem(STOCKINGS_ENABLED_KEY,String(enabled));}catch{}};
 window.addEventListener('storage',e=>{if(e.key===STOCKINGS_ENABLED_KEY||e.key===null)applyEnabled(e.newValue!=='false');});
 applyEnabled(enabled);
 panel.querySelector('button').onclick=()=>{for(const l of legs)l.progress=0;end();status();};
 function uvAt(e,leg){
  const r=canvas.getBoundingClientRect(),point=model.toModelPosition(new PIXI.Point((e.clientX-r.left)/r.width*renderer.screen.width,(e.clientY-r.top)/r.height*renderer.screen.height));
  const v=internal.getDrawableVertices(leg.index),uv=core.getDrawableVertexUvs(leg.index),indices=core.getDrawableVertexIndices(leg.index);
  for(let k=0;k<indices.length;k+=3){
   const a=indices[k]*2,b=indices[k+1]*2,c=indices[k+2]*2;
   const den=(v[b+1]-v[c+1])*(v[a]-v[c])+(v[c]-v[b])*(v[a+1]-v[c+1]);if(Math.abs(den)<1e-8)continue;
   const x=((v[b+1]-v[c+1])*(point.x-v[c])+(v[c]-v[b])*(point.y-v[c+1]))/den;
   const y=((v[c+1]-v[a+1])*(point.x-v[c])+(v[a]-v[c])*(point.y-v[c+1]))/den,z=1-x-y;
   if(x>=-.001&&y>=-.001&&z>=-.001)return 1-(uv[a+1]*x+uv[b+1]*y+uv[c+1]*z);
  }
  return null;
 }
 stage.addEventListener('pointerdown',e=>{
  if(!enabled||busy()||occluded(e)||e.button!==0||e.target.closest('button,input,a,select'))return;
  for(const leg of legs){const y=uvAt(e,leg),edge=.296+.18*leg.progress;if(y===null||Math.abs(y-edge)>.015)continue;
   drag={leg,pointer:e.pointerId,y:e.clientY,start:leg.progress};stage.setPointerCapture(e.pointerId);e.stopImmediatePropagation();e.preventDefault();return;
  }
 },true);
 stage.addEventListener('pointermove',e=>{
  if(!drag||drag.pointer!==e.pointerId)return;
  if(busy()){end();return;}
  const uv=uvAt(e,drag.leg);
  if(uv!==null)drag.leg.progress=Math.max(0,Math.min(1,(uv-.296)/.18));
  else {const h=model.getBounds().height/renderer.screen.height*canvas.getBoundingClientRect().height;drag.leg.progress=Math.max(0,Math.min(1,drag.start+(e.clientY-drag.y)/(h*.37)));}
  e.stopImmediatePropagation();e.preventDefault();status();
 },true);
 stage.addEventListener('pointerup',e=>{if(drag){e.stopImmediatePropagation();e.preventDefault();end();}},true);
 for(const name of ['pointercancel','lostpointercapture'])stage.addEventListener(name,end);
 window.addEventListener('blur',end);
 stage.getStockingState=()=>({enabled,skinReady:setShaderProgress.skinReady,legs:legs.map(l=>({id:l.id,progress:l.progress,strapOpacity:enabled?strapOpacity(l.progress):1,garmentOpacity:enabled?garmentOpacity(l.progress):1})),dragging:!!drag});
 // Transform an authored UV point to screen coordinates for diagnostics.
 stage.getStockingHandles=()=>legs.map(leg=>{
  const uv=core.getDrawableVertexUvs(leg.index),v=internal.getDrawableVertices(leg.index),target=.296+.18*leg.progress;
  let n=0,dist=Infinity;for(let i=0;i<uv.length;i+=2){const d=Math.abs(1-uv[i+1]-target)+Math.abs(uv[i]-.62)*.1;if(d<dist){dist=d;n=i;}}
  const anchor=meshAnchor(v,uv,core.getDrawableVertexIndices(leg.index),target);
  const p=model.worldTransform.apply(internal.localTransform.apply(new PIXI.Point(anchor?.x??v[n],anchor?.y??v[n+1]))),r=canvas.getBoundingClientRect();
  return {id:leg.id,x:r.left+p.x/renderer.screen.width*r.width,y:r.top+p.y/renderer.screen.height*r.height};
 });
}
