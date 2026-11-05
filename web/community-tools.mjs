import {probeParameter} from './parameter-probe.mjs';
import {parameterDiff} from './model-tools.mjs';
import {decodeGif,analyzeTiming} from './community-vendor/gif-analysis.mjs';
export function bindCommunityTools({model,app,profile,busy}){
 const panel=document.getElementById('model-tools');
 panel.innerHTML=`<details open><summary>参数探针 · 独立预览</summary><p>使用模型真实范围。探针暂时关闭此预览的物理更新，结束后恢复；几何变化不等于已确认动作含义。</p><select id="probe-id"></select><p id="probe-range"></p><label>目标值 <input id="probe-value" type="number" step="0.01"></label><label>推荐下限 <input id="probe-min" type="number" step="0.01" placeholder="可留空"></label><label>推荐上限 <input id="probe-max" type="number" step="0.01" placeholder="可留空"></label><label><input id="probe-strict" type="checkbox">限制在推荐范围内</label><button id="probe-run">运行一次探针</button><button id="probe-cancel" disabled>取消并恢复</button><button id="probe-export" disabled>下载探针结果</button><pre id="probe-result" role="status"></pre></details><details><summary>模型参数快照与变化</summary><button id="parameter-export">下载当前参数快照</button><input id="parameter-diff" type="file" accept=".json"><pre id="parameter-result"></pre></details><details><summary>GIF 动作节奏分析</summary><p>在本机分析帧间变化，不自动生成动作语义或预设。变帧间隔保留原时间戳。</p><input id="gif-file" type="file" accept="image/gif,.gif"><button id="gif-export" disabled>下载分析 JSON</button><pre id="gif-result" role="status"></pre></details>`;
 const q=id=>document.getElementById(id);let controller=null,lastProbe,lastGif;
 const download=(data,name)=>{const a=document.createElement('a'),url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
 const raw=model.internalModel.coreModel.getModel();
 const parameters=Array.from(raw.parameters.ids,(id,i)=>({id,min:raw.parameters.minimumValues[i],max:raw.parameters.maximumValues[i],default:raw.parameters.defaultValues[i]}));
 for(const p of parameters){const o=document.createElement('option');o.value=p.id;o.textContent=`${p.id} · ${profile.allParameters.find(x=>x.id===p.id)?.name||''}`;q('probe-id').append(o);}
 q('probe-id').value='AngleX';
 function select(){const p=parameters.find(p=>p.id===q('probe-id').value);q('probe-range').textContent=`真实范围 ${p.min} … ${p.max}，默认值 ${p.default}`;q('probe-value').value=p.default;q('probe-value').min=p.min;q('probe-value').max=p.max;q('probe-min').value='';q('probe-max').value='';}
 q('probe-id').onchange=select;select();
 async function run(options){
  if(controller||busy())throw Error('请先结束录制或当前探针');controller=new AbortController();
  q('probe-run').disabled=true;q('probe-cancel').disabled=false;q('probe-export').disabled=true;
  try{lastProbe=await probeParameter({model,app,...options,signal:controller.signal});const label={'geometry-confirmed':'已确认几何变化并恢复','numeric-only':'仅确认参数写入和恢复；此隔离测试没有观测到几何变化','restore-failed':'恢复检查未通过'}[lastProbe.status];q('probe-result').textContent=label+'\n'+JSON.stringify(lastProbe,null,2);q('probe-export').disabled=false;return lastProbe;}
  catch(e){q('probe-result').textContent=e.message;throw e;}
  finally{controller=null;q('probe-run').disabled=false;q('probe-cancel').disabled=true;}
 }
 q('probe-run').onclick=()=>{const lo=q('probe-min').value,hi=q('probe-max').value;
  if((lo==='')!==(hi==='')){q('probe-result').textContent='推荐上下限需同时填写';return;}
  if(q('probe-value').value===''){q('probe-result').textContent='请填写目标值';return;}
  run({id:q('probe-id').value,value:Number(q('probe-value').value),soft:lo===''?null:[Number(lo),Number(hi)],strict:q('probe-strict').checked}).catch(()=>{});};
 q('probe-cancel').onclick=()=>controller?.abort();q('probe-export').onclick=()=>download(lastProbe,'jingyu-parameter-probe.json');
 q('parameter-export').onclick=()=>download({format:'jingyu-parameters-v1',parameters},'jingyu-parameters.json');
 q('parameter-diff').onchange=async()=>{try{const data=JSON.parse(await q('parameter-diff').files[0].text());if(data.format!=='jingyu-parameters-v1'||!Array.isArray(data.parameters))throw Error('请选择参数快照');q('parameter-result').textContent=JSON.stringify(parameterDiff(data.parameters,parameters),null,2);}catch(e){q('parameter-result').textContent=e.message;}};
 async function analyze(bytes){const result=decodeGif(bytes);if(!result.ok)throw Error(result.error);return {...result,timing:analyzeTiming(result.frames),semanticStatus:'unverified'};}
 q('gif-file').onchange=async()=>{q('gif-export').disabled=true;try{const f=q('gif-file').files[0];if(f.size>32*1024*1024)throw Error('请选择小于 32MB 的 GIF');lastGif=await analyze(new Uint8Array(await f.arrayBuffer()));q('gif-result').textContent=JSON.stringify({meta:lastGif.meta,timing:lastGif.timing},null,2);q('gif-export').disabled=false;}catch(e){q('gif-result').textContent=e.message;}};
 q('gif-export').onclick=()=>download(lastGif,'jingyu-gif-analysis.json');
 window.communityTools={probe:run,cancel:()=>controller?.abort(),parameters,analyzeGif:analyze,get busy(){return !!controller;}};
 window.addEventListener('pagehide',()=>controller?.abort());
}
