const canvas=document.querySelector('#stage'),ctx=canvas.getContext('2d'),slider=document.querySelector('#progress'),status=document.querySelector('#status');
const img=new Image();img.src='/assets/stocking-study/bare-leg-v1.png';
let progress=0,drag=null,edges=[],ready=false;
const W=420,H=800,top=255,bottom=744;
const cloth=document.createElement('canvas');cloth.width=W;cloth.height=H;const c=cloth.getContext('2d');
function bounds(y){return edges[Math.max(0,Math.min(H-1,Math.round(y)))]||{left:180,right:240};}
function render(){
 if(!ready)return;ctx.clearRect(0,0,W,H);ctx.drawImage(img,25,10,370,760);
 const y=top+(bottom-top)*progress,b=bounds(y),cx=(b.left+b.right)/2,r=(b.right-b.left)/2;
 if(progress<.995){
  ctx.save();ctx.beginPath();ctx.rect(0,y,W,H-y);ctx.clip();ctx.drawImage(cloth,0,0);ctx.restore();
  const folds=2+Math.floor(progress*9),depth=9+progress*25;
  for(let i=folds-1;i>=0;i--){
   const fy=y+i*depth/folds,fb=bounds(fy),fr=(fb.right-fb.left)/2;
   ctx.beginPath();ctx.ellipse((fb.left+fb.right)/2,fy,fr+3+progress*6,4+progress*2,0,0,Math.PI*2);
   ctx.fillStyle=i%2?'#edf0f8':'#c3c7db';ctx.fill();ctx.strokeStyle='#9ba2be';ctx.lineWidth=.7;ctx.stroke();
  }
  ctx.beginPath();ctx.ellipse(cx,y,r+5,5,0,0,Math.PI*2);ctx.strokeStyle='#507f70';ctx.lineWidth=2;ctx.stroke();
  ctx.fillStyle='#335f52';ctx.font='13px system-ui';ctx.fillText('↕ 抓住袜口',Math.min(305,b.right+15),y+5);
 }else{
  ctx.fillStyle='#335f52';ctx.font='15px system-ui';ctx.fillText('已拉下 · 向上调进度或重新穿上',85,785);
 }
 slider.value=progress;status.textContent=progress>=.995?'已拉下。点击“重新穿上”恢复。':`袜口下拉 ${Math.round(progress*100)}% · ${drag?'拖动中':'抓住绿色袜口圆环'}`;
 canvas.dataset.progress=progress.toFixed(3);
}
img.onload=()=>{
 c.drawImage(img,25,10,370,760);const data=c.getImageData(0,0,W,H).data;
 for(let y=0;y<H;y++){let left=W,right=0;for(let x=0;x<W;x++)if(data[(y*W+x)*4+3]>120){left=Math.min(left,x);right=Math.max(right,x);}if(right>left)edges[y]={left,right};}
 c.globalCompositeOperation='source-atop';const gradient=c.createLinearGradient(125,0,290,0);gradient.addColorStop(0,'rgba(175,183,208,.94)');gradient.addColorStop(.52,'rgba(250,251,255,.94)');gradient.addColorStop(1,'rgba(186,193,213,.94)');c.fillStyle=gradient;c.fillRect(0,0,W,H);ready=true;render();canvas.dataset.ready='true';
};
img.onerror=()=>{status.textContent='素材加载失败，请刷新重试。';};
function point(e){const r=canvas.getBoundingClientRect();return{x:(e.clientX-r.left)*W/r.width,y:(e.clientY-r.top)*H/r.height};}
canvas.onpointerdown=e=>{if(!ready||e.button!==0||progress>=.995)return;const p=point(e),y=top+(bottom-top)*progress,b=bounds(y);if(Math.abs(p.y-y)>30||p.x<b.left-25||p.x>b.right+25)return;drag={id:e.pointerId,offset:p.y-y};canvas.setPointerCapture(e.pointerId);canvas.style.cursor='grabbing';render();};
canvas.onpointermove=e=>{if(!drag||e.pointerId!==drag.id)return;e.preventDefault();progress=Math.max(0,Math.min(1,(point(e).y-drag.offset-top)/(bottom-top)));render();};
function release(){drag=null;canvas.style.cursor='grab';render();}
canvas.onpointerup=release;canvas.onpointercancel=release;canvas.onlostpointercapture=release;window.addEventListener('blur',release);
slider.oninput=()=>{progress=Number(slider.value);render();};document.querySelector('#reset').onclick=()=>{progress=0;release();};
