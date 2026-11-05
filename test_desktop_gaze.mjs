import assert from 'node:assert/strict';
import {desktopGaze,bindDesktopGaze} from './web/desktop-gaze.mjs';
const model={x:50,y:30,width:300,height:600},window={x:1400,y:300},desktop={width:1920,height:1080};
const point={x:1600,y:426,window,desktop};
assert.deepEqual(desktopGaze(point,model),{x:0,y:0});
assert.equal(desktopGaze({...point,x:0},model).x,-1);
assert.equal(desktopGaze({...point,x:4000},model).x,1);
assert.equal(desktopGaze({...point,y:-1000},model).y,1);
assert.equal(desktopGaze({...point,y:3000},model).y,-1);
// Translating the desktop/window together must preserve the direction on secondary monitors.
assert.deepEqual(desktopGaze({...point,x:point.x-1920,window:{...window,x:window.x-1920}},model),{x:0,y:0});
let listener,enabled=true;const engine={};
const stop=()=>{};
assert.equal(bindDesktopGaze({native:{onPointer:fn=>{listener=fn;return stop;}},engine,geometry:()=>model,enabled:()=>enabled}),stop);
listener({...point,x:0});assert.equal(engine.gaze.x,-1);
enabled=false;listener(point);assert.equal(engine.gaze,null);
console.log('Desktop gaze: global coordinates, multi-monitor origins, clamps and opt-out passed.');
