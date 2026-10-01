import json
import time
import pytest
from well24.engine import Engine
from well24.models import Stimulus,Scan,WELLS
from well24.store import Store


def eventually(predicate,timeout=8):
    end=time.monotonic()+timeout
    while not predicate():
        if time.monotonic()>end: raise AssertionError("Operation timed out")
        time.sleep(.01)


@pytest.fixture
def engine(tmp_path):
    e=Engine(tmp_path);e.connect()
    yield e
    e.close()


def test_manual_load_start_stop(engine):
    job=engine.load(Stimulus(on_s=.03,repetitions=1))
    with pytest.raises(ValueError): engine.start_loaded(1,"stale")
    engine.start_loaded(1,job["id"])
    eventually(lambda:not engine.workers)
    assert job["state"]=="completed"
    assert len(job["completed_blocks"])==1
    assert not any(engine.router.routes.values())


def test_independent_queues_and_conflicts(engine):
    one=engine.enqueue(Stimulus(channel=1,wells=["A1"],on_s=.15))
    two=engine.enqueue(Stimulus(channel=2,wells=["A1"],on_s=.03))
    engine.run_queue([1,2])
    eventually(lambda:two["state"]=="completed")
    assert one["state"]=="completed"
    assert two["started_at"]>=one["ended_at"]


def test_pair_blocks_and_off_time(engine,monkeypatch):
    # Logical schedule test, independent of Windows/antivirus/disk latency.
    # Real-time excess-delay stopping is tested separately below.
    from types import SimpleNamespace
    clock=[0.]
    def logical_wait(cancel,seconds):
        if cancel.is_set(): raise InterruptedError('Operator stop')
        clock[0]+=max(0,seconds)
    monkeypatch.setattr('well24.engine.time',SimpleNamespace(monotonic=lambda:clock[0]))
    monkeypatch.setattr('well24.engine.wait',logical_wait)
    engine.generators[1].done=lambda:True
    job=engine.enqueue(Stimulus(wells=["A1","B1"],on_s=.4,pre_s=.02,post_s=.03,repetitions=2))
    engine.run_queue([1]);eventually(lambda:job["state"] in ("failed","completed"))
    assert job["state"]=="completed"
    assert [b["well"] for b in job["completed_blocks"]]==["A1","B1","A1","B1"]
    for b in job["completed_blocks"][2:]:
        assert .45-1e-9<=b["preceding_off_s"]<.49


def test_pair_delay_fails(engine):
    original=engine.router.route
    def slow(*args): time.sleep(.03);return original(*args)
    engine.router.route=slow
    job=engine.enqueue(Stimulus(wells=["A1","B1"],on_s=.05,repetitions=2))
    engine.run_queue([1]);eventually(lambda:not engine.queue_enabled)
    assert job["state"]=="failed"


def test_stop_does_not_erase_waiting(engine):
    a=engine.enqueue(Stimulus(on_s=2));b=engine.enqueue(Stimulus(wells=["A2"]))
    engine.run_queue([1]);eventually(lambda:a["state"]=="running")
    engine.stop();eventually(lambda:not engine.workers)
    assert a["state"]=="aborted" and b["state"]=="queued"


def test_restart_marks_interrupted(tmp_path):
    e=Engine(tmp_path);job=e.new_job(Stimulus(),"queue");job["state"]="running";e.store.save(job);e.close()
    other=Engine(tmp_path)
    assert other.jobs[0]["state"]=="interrupted"
    assert not other.queue_enabled
    other.close()


@pytest.mark.parametrize("channels",[(1,),(2,),(1,2)])
def test_scan_full_plate(engine,channels):
    engine.connect(channels=channels)
    scan=Scan(wiring_confirmed=True,settling_s=0,cycles=10,sample_rate_hz=50000)
    state=engine.start_scan(scan)
    eventually(lambda:not engine.scan_worker)
    assert state["state"]=="completed",state.get("error")
    assert len(state["results"])==24
    assert set(r["well"] for r in state["results"])==set(WELLS)
    assert all(r["quality"]=="valid" for r in state["results"])
    assert set(r["channel"] for r in state["results"])==set(channels)
    assert not engine.queue_enabled
    folder=engine.store.root/"scans"/state["id"]
    assert len(list(folder.glob("*_HS5_*.csv")))==24
    assert (folder/"results.csv").is_file()


def test_scan_fault_preserves_partial_and_does_not_reassign(engine):
    original=engine.scope.capture;count=0
    def fail(*args):
        nonlocal count
        count+=1
        if count==2: raise RuntimeError("scope disconnected")
        return original(*args)
    engine.scope.capture=fail
    state=engine.start_scan(Scan(wiring_confirmed=True,settling_s=0,cycles=10))
    eventually(lambda:not engine.scan_worker)
    assert state["state"]=="failed" and len(state["results"])==2
    assert not any(g.running for g in engine.generators.values())


def test_scan_exclusive_and_stop(engine):
    state=engine.start_scan(Scan(wiring_confirmed=True,settling_s=2))
    with pytest.raises(ValueError): engine.load(Stimulus())
    with pytest.raises(ValueError): engine.run_queue([1])
    engine.stop();eventually(lambda:not engine.scan_worker)
    assert state["state"]=="aborted"


def test_daily_csv_midnight(tmp_path):
    s=Store(tmp_path)
    s.event("a","queued",{},"2026-09-29T23:59:59+02:00")
    s.event("a","completed",{},"2026-09-30T00:00:01+02:00")
    assert len(list(tmp_path.glob("events_*.csv")))==2
    s.repair_exports()


def test_physical_locked(engine):
    engine.mode="hardware"
    with pytest.raises(ValueError,match="locked"):engine._gate(Stimulus())
    engine.mode="simulation"


def test_logging_failure_stops_and_pauses(engine):
    job=engine.enqueue(Stimulus(on_s=.02))
    next_job=engine.enqueue(Stimulus(on_s=.02))
    def fail(*args,**kwargs): raise OSError("disk full")
    engine.store.event=fail
    engine.run_queue([1])
    eventually(lambda:job["state"]=="failed" and not engine.workers)
    assert next_job["state"]=="queued"
    assert not engine.queue_enabled
    assert not any(g.running for g in engine.generators.values())
    assert not any(engine.router.routes.values())


def test_stop_loaded_survives_failed_log(engine):
    engine.load(Stimulus())
    def fail(*args,**kwargs): raise OSError("disk full")
    engine.store.event=fail
    engine.stop()
    assert not engine.loaded and not engine.reserved
    assert engine.error
    assert not any(g.running for g in engine.generators.values())


def test_restart_scan_and_explicit_recovery(tmp_path):
    e=Engine(tmp_path)
    folder=tmp_path/"scans"/"old"
    folder.mkdir(parents=True)
    e._save_scan(folder,{"id":"old","state":"running","results":[]})
    job=e.new_job(Stimulus(),"queue");job["state"]="running";e.store.save(job)
    e.close()
    other=Engine(tmp_path)
    try:
        assert other.scan_state["state"]=="interrupted"
        assert json.loads((folder/"scan.json").read_text())["state"]=="interrupted"
        replacement=other.recover_entry(job["id"])
        assert replacement["state"]=="queued" and replacement["params"]==job["params"]
        assert replacement["id"]!=job["id"] and not other.queue_enabled
    finally: other.close()


def test_shared_route_failure_stops_other_channel(engine):
    one=engine.enqueue(Stimulus(channel=1,on_s=2))
    two=engine.enqueue(Stimulus(channel=2,wells=["A2"],on_s=2))
    engine.run_queue([1,2]);eventually(lambda:one["state"]==two["state"]=="running")
    engine.shared_fault("Lost Arduino heartbeat")
    eventually(lambda:not engine.workers)
    assert not any(g.running for g in engine.generators.values())
    assert not engine.queue_enabled
    with pytest.raises(ValueError,match="Reconnect"): engine.load(Stimulus())
