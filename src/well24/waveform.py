"""Control formulas follow HS5 waveform.py; ramp is sampled without peak renormalization.

Unlike the legacy normalization, a partial cycle never becomes a larger signal.
Only the on block is allocated. Preview evaluates the same formula at actual sample indices.
"""
import numpy as np
from .models import Stimulus


def plan(p: Stimulus, max_samples=67_108_864, max_rate=240_000_000):
    highest = p.frequency_hz + (p.delta_hz if p.mode == "tis_like" else 0)
    rate = max(1000., highest * 50, 8 / p.on_s)
    if rate > max_rate or round(rate * p.on_s) > max_samples:
        raise ValueError("This on block does not fit at 50 samples/cycle. Shorten the on block or lower frequency; off periods/repetitions do not consume waveform memory.")
    n = round(rate * p.on_s)
    return {"sample_rate_hz": rate, "samples": n, "actual_on_s": n / rate,
            "nominal_pair_off_s": p.pair_off_s,
            "duration_quantization_s": n / rate - p.on_s}


def samples(p: Stimulus, indices, rate):
    t = np.asarray(indices, dtype=float) / rate
    phase = (t * p.frequency_hz) % 1
    if p.mode == "tis_like":
        y = .5 * (np.cos(2*np.pi*p.frequency_hz*t) - np.cos(2*np.pi*(p.frequency_hz+p.delta_hz)*t))
    elif p.shape == "sine":
        y = np.sin(2*np.pi*p.frequency_hz*t)
    elif p.shape in ("triangle", "ramp"):
        # Preserve the HS5 Ramp behavior (symmetric triangular ramp).
        y = np.where(phase < .5, 4*phase-1, 3-4*phase)
    else:
        duty = p.pulse_width_s*p.frequency_hz if p.pulse_width_s is not None else .5
        y = np.where(phase < duty, 1., -1.)
    if p.ramp_s:
        last = (round(p.on_s*rate)-1)/rate
        y *= np.clip(np.minimum(t/p.ramp_s, (last-t)/p.ramp_s), 0, 1)
    return y.astype(np.float32)


def build(p, rate=None, max_samples=67_108_864):
    info = plan(p, max_samples)
    rate = rate or info["sample_rate_hz"]
    highest = p.frequency_hz + (p.delta_hz if p.mode == "tis_like" else 0)
    n = round(p.on_s*rate)
    if n < 8 or n > max_samples or rate < highest*50:
        raise ValueError("Accepted device sample rate cannot represent this on block")
    return samples(p, np.arange(n), rate)


def protocol_timing(p):
    return p.cycle_s, 0 if p.off_s is not None else p.pre_s


# Like HS5's min/max overview, preserve extrema instead of sparsely sampling
# a carrier. Only one reusable on block is inspected, in bounded chunks.
from functools import lru_cache
import json


@lru_cache(maxsize=2)
def _block_extrema(config, rate):
    p = Stimulus(**json.loads(config))
    n = round(p.on_s*rate)
    step = max(1, int(np.ceil(n/8192)))
    lows, highs = [], []
    for start in range(0,n,step*64):
        y = samples(p,np.arange(start,min(n,start+step*64)),rate)*p.amplitude_ma
        edges = np.arange(0,len(y),step)
        lows.extend(np.minimum.reduceat(y,edges))
        highs.extend(np.maximum.reduceat(y,edges))
    return step,np.asarray(lows),np.asarray(highs)


def preview(p, well=None, start=0., end=None, accepted_rate=None):
    info=plan(p)
    rate=accepted_rate or info['sample_rate_hz']
    info.update(sample_rate_hz=rate,samples=round(p.on_s*rate),actual_on_s=round(p.on_s*rate)/rate)
    well=well or p.wells[0]
    if well not in p.wells: raise ValueError('Preview well must be selected')
    cycle,lead=protocol_timing(p)
    initial=p.initial_off_s
    total=p.duration_s if p.duration_s is not None else initial+cycle*2
    shown=max(1,int(np.ceil((total-initial)/cycle)))
    end=min(total if end is None else end,total)
    if not np.isfinite(total) or total*rate>2**53 or start<0 or end<=start: raise ValueError('Invalid preview window')
    count=int(np.ceil((end-start)*rate))+1
    curves={}
    carrier_cycles=(end-start)*(p.frequency_hz+(p.delta_hz if p.mode=='tis_like' else 0))
    # Even a fully sampled carrier aliases visually when many cycles occupy a
    # single screen pixel. Show its extrema until individual cycles are legible.
    if count<=50000 and carrier_cycles<=100:
        t=np.linspace(start,end,max(2,count))
        for w in p.wells:
            local=(t-initial)%cycle-lead-p.wells.index(w)*p.on_s
            block_start=initial+np.floor((t-initial)/cycle)*cycle+lead+p.wells.index(w)*p.on_s
            mask=(local>=0)&(local<p.on_s)&(t>=initial)&(t<total)&(block_start+p.on_s<=total+1e-9)
            y=np.zeros(len(t));idx=np.floor(local[mask]*rate).astype(int)
            y[mask]=samples(p,idx,rate)*p.amplitude_ma
            curves[w]=y.tolist()
        kind='samples'
    else:
        step,lows,highs=_block_extrema(p.model_dump_json(),rate)
        n=info['samples']
        def extrema(a,b):
            lo=max(0,int(np.floor(a*rate)));hi=min(n,int(np.ceil(b*rate)))
            if hi<=lo:return 0.,0.
            first=(lo+step-1)//step;last=hi//step
            low,high=float('inf'),-float('inf')
            if first<last:low=float(lows[first:last].min());high=float(highs[first:last].max())
            for aa,bb in ((lo,min(hi,first*step)),(max(lo,last*step,first*step),hi)):
                if bb>aa:
                    y=samples(p,np.arange(aa,bb),rate)*p.amplitude_ma
                    low=min(low,float(y.min()));high=max(high,float(y.max()))
            return low,high
        buckets=max(2,min(2000,int(carrier_cycles//2)))
        edges=np.linspace(start,end,buckets+1)
        # Keep block boundaries explicit, so the envelope cannot paint current
        # into an adjacent off interval or the initial trigger preparation.
        if shown<=2000:
            boundaries=[initial+rep*cycle+lead+k*p.on_s
                        for rep in range(shown) for k in range(len(p.wells)+1)]
            edges=np.unique(np.concatenate((edges,[x for x in boundaries if start<x<end])))
        t=np.repeat(edges,2)[1:-1]
        for wi,w in enumerate(p.wells):
            offset=initial+lead+wi*p.on_s;y=[]
            for a,b in zip(edges[:-1],edges[1:]):
                first=max(0,int(np.floor((a-offset-p.on_s)/cycle))+1)
                last=min((p.block_count(wi) if p.duration_s is not None else shown)-1,int(np.ceil((b-offset)/cycle))-1)
                lo,hi=0.,0. # Include the zero baseline when a bucket crosses an off period.
                if first<=last:
                    for rep in set((first,last)):
                        aa=max(0,a-rep*cycle-offset);bb=min(p.on_s,b-rep*cycle-offset)
                        if bb>aa:
                            l,h=extrema(aa,bb);lo=min(lo,l);hi=max(hi,h)
                    if last-first>1:lo=min(lo,float(lows.min()));hi=max(hi,float(highs.max()))
                y.extend((lo,hi))
            curves[w]=y
        kind='minmax_envelope'
    return {**info,'time':t.tolist(),'current_ma':curves[well],'currents_by_well':curves,'well':well,'representation':kind,
            'note':('Device-accepted rate. ' if accepted_rate else 'Planned rate. ')+
                   ('Full-rate waveform samples. ' if kind=='samples' else 'Min/max amplitude envelope; carrier cycles are unresolved at this scale. Zoom in to see actual samples. ')+
                   'Nominal commanded current; switching overhead excluded.'}
