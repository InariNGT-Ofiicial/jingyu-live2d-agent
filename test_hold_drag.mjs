import assert from 'node:assert/strict';
import {dragValues} from './web/hold-drag.mjs';
assert.deepEqual(dragValues('chest',.24,-.2),{zone:'chest',x:1,y:1});
assert.deepEqual(dragValues('head',-.24,.2),{zone:'head',x:-1,y:-1});
assert.equal(dragValues('head',.06,0).x,.5);
console.log('Hold drag: normalized displacement, direction and bounds passed.');
