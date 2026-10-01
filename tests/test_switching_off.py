import time
from types import SimpleNamespace
import numpy as np
import pytest
from fastapi.testclient import TestClient
from well24.app import create_app
from well24.engine import Engine
from well24.models import Stimulus
from well24.queue_csv import encode,decode
from well24.queue_summary import summarize
from well24.waveform import preview,plan


@pytest.mark.parametrize('on,off',[(10,10),(10,20),(.4,.9)])
def test_execution_off_interval_and_total(tmp_path,monkeypatch,on,off):
    e=Engine(tmp_path);e.connect()
    clock=[0.]
    def wait(cancel,seconds):
        if cancel.is_set():raise InterruptedError('stop')
        clock[0]+=max(0,seconds)
    monkeypatch.setattr('well24.engine.time',SimpleNamespace(monotonic=lambda:clock[0]))
    monkeypatch.setattr('well24.engine.wait',wait)
    e.generators[1].done=lambda:True
    try:
        p=Stimulus(wells=['A1','D5'],on_s=on,off_s=off,repetitions=3)
        j=e.enqueue(p);e.run_queue([1]);deadline=time.monotonic()+8
        while j['state'] not in ('completed','failed') and time.monotonic()<deadline:time.sleep(.005)
        assert j['state']=='completed',j.get('error')
        assert [b['well'] for b in j['completed_blocks']]==['A1','D5']*3
        assert clock[0]==pytest.approx(3*(on+off),abs=.01)
        for b in j['completed_blocks'][2:]:assert b['preceding_off_s']==pytest.approx(off,abs=.003)
        assert plan(p)['nominal_pair_off_s']==off
    finally:e.close()


def test_preview_timing_and_concurrent_queue():
    p=Stimulus(wells=['A1','D5'],frequency_hz=1,on_s=10,off_s=20,repetitions=3)
    out=preview(p,end=40);t=np.asarray(out['time']);a=np.asarray(out['currents_by_well']['A1']);b=np.asarray(out['currents_by_well']['D5'])
    assert out['representation']=='samples'
    assert np.all(a[(t>=10)&(t<30)]==0)
    assert np.all(b[(t<10)|((t>=20)&(t<40))]==0)
    assert max(abs(a[(t>30)&(t<40)]))>.99
    assert max(abs(b[(t>10)&(t<20)]))>.99
    assert np.all(a*b==0)
    assert preview(p)['time'][-1]==90
    jobs=[{'id':str(ch),'kind':'queue','state':'queued','params':p.model_copy(update={'channel':ch,'wells':ws}).model_dump()} for ch,ws in [(1,['A1','D5']),(2,['B1','C5'])]]
    q=summarize(jobs);assert q['estimated_seconds']==90 and q['unique_wells']==4


def test_invalid_off_rejected_before_queue(tmp_path):
    with TestClient(create_app(tmp_path)) as c:
        p=Stimulus(wells=['A1','A2']).model_dump();p['off_s']=.5
        r=c.post('/api/queue',json=p)
        assert r.status_code==422 and 'OFF period is shorter' in r.text
        assert c.get('/api/status').json()['jobs']==[]
    with pytest.raises(ValueError):Stimulus(off_s=1)
    with pytest.raises(ValueError):Stimulus(wells=['A1','A2'],off_s=1,pre_s=1)


def test_new_and_legacy_queue_templates():
    new=Stimulus(wells=['A1','D5'],on_s=10,off_s=20)
    text=encode([{'kind':'queue','params':new.model_dump()}])
    assert decode(text)==[new]
    # Historic v1 files have no OFF column and must not be reinterpreted.
    old=Stimulus(wells=['A1','D5'],on_s=10,pre_s=2,post_s=3)
    import csv,io
    reader=csv.DictReader(io.StringIO(encode([{'kind':'queue','params':old.model_dump()}]).lstrip('\ufeff')))
    rows=list(reader);fields=[f for f in reader.fieldnames if f not in ('off_s','stimulation_time_s')]
    out=io.StringIO();writer=csv.DictWriter(out,fieldnames=fields);writer.writeheader()
    for row in rows:row.pop('off_s');row.pop('stimulation_time_s');row['format_version']='1';writer.writerow(row)
    restored=decode(out.getvalue())[0]
    assert restored==old and restored.cycle_s==25 and restored.pair_off_s==15


def test_trigger_preparation_is_initial_only():
    p=Stimulus(wells=['A1','A2'],on_s=1,off_s=2,repetitions=2,trigger_out=True)
    assert p.initial_off_s==.105 and p.cycle_s==3
    out=preview(p)
    assert out['time'][-1]==6.105
    initial=np.asarray(out['time'])<.105
    assert np.all(np.asarray(out['currents_by_well']['A1'])[initial]==0)
