import threading
from types import SimpleNamespace
import numpy as np
import pytest
from well24.engine import Engine
from well24.models import Stimulus
from well24.waveform import preview
from well24.queue_csv import encode,decode
from well24.queue_summary import summarize


def run_clock(tmp_path,monkeypatch,p,route_delay=.02,log_delay=.005):
    e=Engine(tmp_path);e.connect();clock=[0.];loads=[];starts=[]
    def delay(dt):clock[0]+=dt
    def wait(cancel,seconds):
        if cancel.is_set():raise InterruptedError('stop')
        delay(max(0,seconds))
    monkeypatch.setattr('well24.engine.time',SimpleNamespace(monotonic=lambda:clock[0]))
    monkeypatch.setattr('well24.engine.wait',wait)
    g=e.generators[1]
    def load(p):loads.append(p);delay(2);return {'actual_on_s':p.on_s,'sample_rate_hz':1000,'samples':round(p.on_s*1000)}
    g.load=load;g.done=lambda:True;g.start=lambda:(delay(.001),starts.append(clock[0]));g.stop=lambda:delay(.001)
    original=e.router.route
    def route(*args):delay(route_delay);return original(*args)
    e.router.route=route
    # Inject bounded durable-log latency without real-time waits or quadratic
    # test disk writes. Persistence is exercised separately by engine/API tests.
    e.store.save=lambda j:delay(log_delay)
    e.store.event=lambda *args,**kwargs:delay(log_delay)
    job=e.new_job(p,'queue');e.jobs.append(job)
    try:e._run(job,threading.Event())
    finally:e.close()
    return job,loads,starts


@pytest.mark.parametrize('hours',[1,2])
def test_long_timed_switching_bounded_latency(tmp_path,monkeypatch,hours):
    p=Stimulus(wells=['A1','B1'],on_s=10,off_s=20,repetitions=0,stimulation_time_s=3600*hours)
    j,loads,starts=run_clock(tmp_path,monkeypatch,p)
    assert j['state']=='completed',j.get('error')
    assert len(loads)==1 and len(starts)==240*hours
    assert all(b['host_start_s']+b['host_elapsed_s']<=p.duration_s for b in j['completed_blocks'])
    for b in j['completed_blocks'][2:]:
        assert b['preceding_off_s']>=20-1e-9
        assert b['start_lateness_s']<1
    # Deadlines retain one fixed origin across hours of operation.
    assert j['completed_blocks'][-1]['scheduled_start_s']==3600*hours-20


def test_no_slack_eventually_rejects_accumulated_latency(tmp_path,monkeypatch):
    p=Stimulus(wells=['A1','B1'],on_s=.1,off_s=.1,repetitions=0,stimulation_time_s=3600)
    j,_,_=run_clock(tmp_path,monkeypatch,p,route_delay=.002,log_delay=.001)
    assert j['state']=='failed'
    assert 'deadline missed' in j['error'] or 'off interval' in j['error']


def test_long_route_delay_fails_visibly(tmp_path,monkeypatch):
    p=Stimulus(wells=['A1','B1'],on_s=1,off_s=2,repetitions=2)
    j,_,_=run_clock(tmp_path,monkeypatch,p,route_delay=.2)
    assert j['state']=='failed' and 'deadline missed' in j['error']


def test_timed_cutoff_does_not_truncate_block(tmp_path,monkeypatch):
    p=Stimulus(wells=['A1','B1'],frequency_hz=1,on_s=10,off_s=20,repetitions=0,stimulation_time_s=45)
    j,_,_=run_clock(tmp_path,monkeypatch,p)
    assert j['state']=='completed'
    assert [b['well'] for b in j['completed_blocks']]==['A1','B1','A1']
    assert all(b['host_elapsed_s']>=10 for b in j['completed_blocks'])
    out=preview(p,start=30,end=45);t=np.asarray(out['time'])
    assert max(abs(np.asarray(out['currents_by_well']['A1'])[t<40]))>.99
    assert np.all(np.asarray(out['currents_by_well']['B1'])==0)
    assert decode(encode([{'kind':'queue','params':p.model_dump()}]))==[p]
    assert summarize([{'kind':'queue','id':'x','state':'queued','params':p.model_dump()}])['estimated_seconds']==45


def test_connect_does_not_enqueue(tmp_path,monkeypatch):
    e=Engine(tmp_path)
    try:
        assert e.jobs==[]
        e.connect('simulation');assert e.jobs==[]
        # Hardware connection fails closed without a profile; it cannot seed a job.
        monkeypatch.setattr('well24.engine.discover',lambda profile:{})
        try:e.connect('hardware')
        except (ValueError,RuntimeError):pass
        assert e.jobs==[]
    finally:e.close()


def test_remove_only_identified_entry_retains_audit(tmp_path):
    e=Engine(tmp_path)
    try:
        one=e.enqueue(Stimulus(wells=['D5']))
        two=e.enqueue(Stimulus(wells=['B1']))
        e.remove_entry(one['id'])
        assert [j['id'] for j in e.status()['jobs']]==[two['id']]
        assert len(e.store.jobs())==2
        assert e.store.recent()[0]['state']=='entry_removed'
    finally:e.close()
