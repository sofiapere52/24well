"""Nominal queue schedule: independent channels, FIFO and whole-entry well reservations."""
from .models import Stimulus
def summarize(jobs, elapsed=None):
    elapsed=elapsed or {}
    pending=[j for j in jobs if j['kind']=='queue' and j['state'] in ('queued','loading','waiting_trigger','running')]
    by_channel={1:[],2:[]};free={1:0.,2:0.};well_free={};per_well={};blocks=0;uncertain=False
    for j in pending:
        p=j['params'];protocol=Stimulus(**p)
        duration=protocol.duration_s
        remaining=max(0.,duration-elapsed.get(j['id'],0.))
        blocks+=max(0,protocol.block_count()-len(j.get('completed_blocks',[])))
        uncertain |= p.get('trigger_in',False)
        for w in p['wells']: per_well[w]=per_well.get(w,0.)+remaining
        if j['state']!='queued':
            free[p['channel']]=remaining
            for w in p['wells']:well_free[w]=remaining
        else:by_channel[p['channel']].append((j,remaining))
    while any(by_channel.values()):
        choices=[]
        for ch,q in by_channel.items():
            if q:
                j,duration=q[0]
                start=max(free[ch],*(well_free.get(w,0.) for w in j['params']['wells']))
                choices.append((start,ch,j,duration))
        start,ch,j,duration=min(choices,key=lambda x:(x[0],x[1]))
        finish=start+duration;free[ch]=finish;by_channel[ch].pop(0)
        for w in j['params']['wells']:well_free[w]=finish
    return {'entries':len(pending),'unique_wells':len(per_well),'well_blocks':blocks,
            'estimated_seconds':max(free.values()),'per_well_protocol_s':dict(sorted(per_well.items())),
            'trigger_wait_unbounded':uncertain,
            'note':'Assumes both queues run when available. Excludes loading, switching and external-trigger waits. Paired wells share the full paired protocol duration; do not add their durations to estimate finish time.'}
