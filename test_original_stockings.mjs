import assert from 'node:assert/strict';
import {installStockingShader,meshAnchor,strapOpacity,garmentOpacity} from './web/original-stockings.mjs';
let shader='',values=[],draws=0;
const gl={shaderSource:(s,t)=>shader=t,useProgram:()=>{},drawElements:()=>draws++,getUniformLocation:(p,name)=>p.stocking&&name==='jyStockingProgress'?'sock':null,uniform1f:(l,v)=>values.push(v)};
const set=installStockingShader(gl),program={stocking:true};
gl.shaderSource({},'precision mediump float;uniform sampler2D s_texture0;vec4 bridgeColor(vec2 uv){vec4 c=texture2D(s_texture0,uv);return c;}');
assert(shader.includes('uniform float jyStockingProgress'));assert(shader.includes('jyStocking(texture2D'));
gl.useProgram(program);set(.5);gl.drawElements();set(-1);gl.drawElements();assert.deepEqual(values,[.5,-1]);
gl.useProgram({stocking:false});gl.drawElements();assert.equal(values.length,2);assert.equal(draws,3);
gl.shaderSource({},'mask shader');assert.equal(shader,'mask shader');
console.log('Original stockings: material shader isolation, per-draw reset and unmodified masks passed.');

const anchor=meshAnchor([0,0,2,0,0,4,2,4],[0,1,1,1,0,0,1,0],[0,1,2,1,3,2],.5);
assert.deepEqual(anchor,{x:1,y:2,width:2});
assert.equal(meshAnchor([0,0,2,0,0,4],[0,1,1,1,0,0],[0,1,2],2),null);
console.log('Original lace: UV row follows original deformed mesh cross-section.');

assert.equal(strapOpacity(0),1);assert.equal(strapOpacity(1),0);assert(Math.abs(strapOpacity(.15)-.5)<1e-8);assert(strapOpacity(.1)>strapOpacity(.2));

assert.equal(garmentOpacity(0),1);assert.equal(garmentOpacity(.9),1);assert(Math.abs(garmentOpacity(.96)-.5)<1e-8);assert.equal(garmentOpacity(1),0);

const {stockingsEnabled,STOCKINGS_ENABLED_KEY}=await import('./web/original-stockings.mjs');
for(const [saved,expected] of [[null,true],['true',true],['false',false]])assert.equal(stockingsEnabled({getItem:key=>{assert.equal(key,STOCKINGS_ENABLED_KEY);return saved;}}),expected);
assert.equal(stockingsEnabled({getItem:()=>{throw Error('Storage unavailable');}}),true);
console.log('Clothing defaults: enabled on first use, explicit off retained, unavailable storage supported.');
