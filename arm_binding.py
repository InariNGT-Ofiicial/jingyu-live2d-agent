"""Conservative gesture-relative 2D arm coupling, not skeletal IK."""
import math

def sample(points,t):
    if t<=points[0][0]:return points[0][1]
    for (a,x),(b,y) in zip(points,points[1:]):
        if t<=b:
            u=max(0,min(1,(t-a)/max(1e-8,b-a)))
            return x+(y-x)*u*u*(3-2*u)
    return points[-1][1]

def clamp(v,a,b):return max(a,min(b,v))

def bind_arm_tracks(tracks,joints,rest,start,end,limits):
    """Couple only the hold interval; preserve authored entry/exit and switches."""
    by_id={t['id']:t for t in tracks}
    required=['upperArm','forearm','wrist','perspective']
    if any(joints[k] not in by_id for k in required):return False
    original={k:list(by_id[joints[k]]['points']) for k in required}
    # Share timestamps so individually keyed joints cannot drift in interpolation.
    times={round(start,5),round(end,5)}
    times.update(t for points in original.values() for t,_ in points if start<t<end)
    count=max(1,math.ceil((end-start)*45))
    times.update(round(start+(end-start)*i/count,5) for i in range(count+1))
    output={k:[] for k in required};changed=False
    for t in sorted(times):
        raw={k:sample(original[k],t) for k in required}
        delta={k:raw[k]-rest[k] for k in required}
        # Work in normalized model controls relative to this gesture's authored pose.
        upper=clamp(delta['upperArm']+.18*delta['forearm'],-.42,.42)
        perspective=clamp(delta['perspective'],-.22,.22)
        center=.45*upper
        allowance=.32*(1-.35*min(1,abs(perspective)/.22))
        residual=clamp(delta['forearm'],-allowance,allowance)
        forearm=center+residual
        wrist=clamp(delta['wrist']-.2*forearm,-.38,.38)
        desired={'upperArm':upper,'forearm':forearm,'wrist':wrist,'perspective':perspective}
        edge=clamp(min(t-start,end-t)/.25,0,1);edge=edge*edge*(3-2*edge)
        for k in required:
            value=raw[k]+(rest[k]+desired[k]-raw[k])*edge
            p=limits[joints[k]];value=clamp(value,p['min'],p['max'])
            changed|=abs(value-raw[k])>.00001
            output[k].append([t,round(value,6)])
    for k in required:
        tr=by_id[joints[k]]
        tr['points']=[p for p in original[k] if p[0]<start]+output[k]+[p for p in original[k] if p[0]>end]
        tr['armBinding']='gesture-relative-v1'
    return changed
