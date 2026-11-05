import {readFileSync} from 'node:fs';
import {communityPlan} from './web/community-adapters.mjs';
try {
  const request=JSON.parse(readFileSync(0,'utf8'));
  const parameters=JSON.parse(readFileSync(new URL('./core-inventory.json',import.meta.url),'utf8')).parameters;
  console.log(JSON.stringify(communityPlan(request.source,request.payload,parameters)));
} catch(e) {console.error(e.message);process.exitCode=1;}
