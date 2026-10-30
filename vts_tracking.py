"""Realtime tracking injection, strictly limited to representable author mappings."""
import argparse,json,time
from pathlib import Path
from model_profile import MODEL_ROOT,read_json
from vts_adapter import export_calibration
from vts_client import VTS

def play(plan,port=8001):
    export=export_calibration(plan)
    if not export['representable']:raise ValueError('Plan cannot use author tracking mappings: '+json.dumps(export['blockers'],ensure_ascii=True))
    frames=export['frames'];v=VTS(port);result={'status':'running','sent':0,'skipped':0,'samples':[],'fps':export['fps'],'duration':export['duration']};last=None
    try:
        v.authenticate();model_id=read_json(MODEL_ROOT/'大肥鱼.vtube.json')['ModelID'];v.require_model(model_id)
        start=time.perf_counter();index=0;next_read=0
        while index<len(frames):
            frame=frames[index];time.sleep(max(0,start+frame['time']-time.perf_counter()))
            # Send the newest due frame; never burst stale poses after a stall.
            elapsed=time.perf_counter()-start
            while index+1<len(frames) and frames[index+1]['time']<=elapsed:
                index+=1;result['skipped']+=1
            frame=frames[index];last=frame['request']['data']
            v.call('InjectParameterDataRequest',last);result['sent']+=1;index+=1
            if elapsed>=next_read:
                r=v.call('Live2DParameterListRequest')
                if r.get('modelID')!=model_id:raise RuntimeError('Model changed during stream')
                result['samples'].append({'time':elapsed,'values':{p['name']:p['value'] for p in r['parameters']}});next_read=elapsed+.25
        result['status']='stream-complete'
    finally:
        try:
            if last:v.call('InjectParameterDataRequest',{'faceFound':False,'mode':'set','parameterValues':[{**p,'weight':0} for p in last['parameterValues']]})
        finally:v.close()
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('plan');p.add_argument('--port',type=int,default=8001);p.add_argument('--output',required=True);a=p.parse_args()
    r=play(read_json(Path(a.plan)),a.port);Path(a.output).write_text(json.dumps(r,ensure_ascii=False),encoding='utf-8');print(json.dumps({k:v for k,v in r.items() if k!='samples'}))
