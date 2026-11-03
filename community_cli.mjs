import {readFileSync} from 'node:fs';
import {communityPlan} from './web/community-adapters.mjs';
try {
  const request=JSON.parse(readFileSync(0,'utf8'));
  console.log(JSON.stringify(communityPlan(request.source,request.payload)));
} catch(e) {console.error(e.message);process.exitCode=1;}
