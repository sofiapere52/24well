import time
import pytest
from fastapi.testclient import TestClient
from well24.app import create_app
from well24.browser_lifetime import BrowserLifetime
from well24.engine import Engine
from well24.models import Stimulus
from well24.queue_csv import encode, decode


def eventually(predicate, timeout=8):
    end = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > end: raise AssertionError('Operation timed out')
        time.sleep(.01)


@pytest.fixture
def engine(tmp_path):
    e = Engine(tmp_path); e.connect()
    yield e
    e.close()


def test_finished_queue_pauses_so_new_entries_wait_for_run(engine):
    first = engine.enqueue(Stimulus(on_s=.03))
    engine.run_queue([1])
    eventually(lambda: first['state'] == 'completed' and not engine.queue_enabled)
    later = engine.enqueue(Stimulus(on_s=.03))
    time.sleep(.2)
    assert later['state'] == 'queued' and not engine.busy()
    engine.load(Stimulus()); engine.stop()


def test_run_requires_pending_entries(engine):
    with pytest.raises(ValueError, match='No pending entries'):
        engine.run_queue([1, 2])
    engine.enqueue(Stimulus(channel=2, on_s=2))
    engine.run_queue([1, 2])
    assert engine.queue_enabled == {2}
    engine.stop()


def test_back_to_back_single_well_blocks_rejected_before_running(engine):
    for p in (Stimulus(on_s=1, repetitions=4), Stimulus(on_s=1, repetitions=0, stimulation_time_s=5)):
        with pytest.raises(ValueError, match='pre-off \\+ post-off'):
            engine.enqueue(p)
        with pytest.raises(ValueError, match='pre-off \\+ post-off'):
            engine.load(p)
    assert not engine.reserved and not engine.loaded
    engine.enqueue(Stimulus(on_s=1, repetitions=1))
    engine.enqueue(Stimulus(on_s=1, post_s=.1, repetitions=4))
    engine.enqueue(Stimulus(wells=['A1', 'B1'], on_s=1, off_s=1, repetitions=4))
    csv = encode([{'kind': 'queue', 'params': Stimulus(on_s=1, repetitions=4).model_dump()}])
    with pytest.raises(ValueError, match='CSV row 2: Repeated blocks'):
        decode(csv)


def test_stored_entry_violating_gap_fails_without_stopping_dispatcher(engine):
    bad = engine.new_job(Stimulus(on_s=.03, post_s=.2, repetitions=2), 'queue')
    bad['params']['post_s'] = 0
    engine.jobs.append(bad)
    good = engine.enqueue(Stimulus(on_s=.03))
    engine.run_queue([1])
    eventually(lambda: bad['state'] == 'failed')
    assert 'Repeated blocks' in bad['error'] and engine.dispatcher.is_alive()
    engine.run_queue([1])
    eventually(lambda: good['state'] == 'completed')


def test_arduino_led_states(tmp_path, monkeypatch):
    e = Engine(tmp_path)
    try:
        assert e.status()['arduino']['state'] == 'disconnected'
        e.connect()
        assert e.status()['arduino'] == {'state': 'ready', 'label': 'Simulated', 'detail': 'Simulated PCB'}
        e.router.failed = True
        assert e.status()['arduino']['state'] == 'error'
    finally:
        e.router.failed = False; e.close()
    from well24.routing import SerialRouter
    clock = [100.]
    monkeypatch.setattr('well24.routing.time.monotonic', lambda: clock[0])
    router = object.__new__(SerialRouter)
    router.failed, router.port, router.last_ok = False, 'COM7', None
    assert router.health()['label'] == 'No reply'
    router.last_ok = 99.
    assert router.health() == {'state': 'ready', 'label': 'Connected', 'detail': 'COM7'}
    clock[0] = 103.5
    assert router.health()['state'] == 'error'
    router.last_ok, router.failed = 103., True
    assert router.health()['label'] == 'Fault · reconnect'


def test_unexpected_server_error_is_readable_json(monkeypatch, tmp_path):
    monkeypatch.setattr(Engine, 'scan_plan', lambda self, s: {}['missing'])
    with TestClient(create_app(tmp_path), raise_server_exceptions=False) as c:
        r = c.post('/api/scan/plan', json={})
        assert r.status_code == 500
        assert 'KeyError' in r.json()['detail']
        failure = next(e for e in c.get('/api/status').json()['events'] if e['state'] == 'action_failed')
        assert failure['details']['action'] == 'Show well assignments' and 'KeyError' in failure['details']['error']
    assert 'Traceback' in (tmp_path / 'server_errors.log').read_text(encoding='utf-8')


def test_failed_actions_are_in_live_log_with_plain_messages(monkeypatch, tmp_path):
    monkeypatch.setattr('well24.engine.ROOT', tmp_path)
    with TestClient(create_app(tmp_path)) as c:
        r = c.post('/api/connect', json={'mode': 'hardware'})
        assert r.status_code == 400 and 'hardware.json is missing' in r.json()['detail']
        bad = c.post('/api/queue', json={**Stimulus().model_dump(), 'ramp_s': 5})
        assert bad.json()['detail'] == 'Ramp up and down must fit within the on block'
        events = [e for e in c.get('/api/status').json()['events'] if e['state'] == 'action_failed']
        assert {e['details']['action'] for e in events} == {'Connect devices', 'Add to queue'}
        (tmp_path / 'hardware.json').write_text('{"generators": {', encoding='utf-8')
        assert 'not valid JSON (line 1' in c.post('/api/connect', json={'mode': 'hardware'}).json()['detail']


def test_hardware_connects_without_acceptance_or_arduino_but_never_stimulates(monkeypatch, tmp_path):
    import json
    from well24.devices import MockGenerator
    from well24.models import Scan
    from well24.routing import MockRouter
    monkeypatch.setattr('well24.engine.ROOT', tmp_path)
    (tmp_path / 'hardware.json').write_text(json.dumps({'generators': {'1': '42473', '2': '42487'}, 'arduino_port': ''}))
    monkeypatch.setattr('well24.engine.discover', lambda profile: {1: MockGenerator(1), 2: MockGenerator(2)})
    e = Engine(tmp_path)
    try:
        status = e.connect('hardware')
        assert status['mode'] == 'hardware' and len(status['devices']) == 2
        assert status['arduino']['state'] == 'disconnected'
        for attempt in (lambda: e.load(Stimulus()), lambda: e.start_scan(Scan(wiring_confirmed=True))):
            with pytest.raises(ValueError, match='Arduino PCB is not connected'): attempt()
        e.router = MockRouter()
        with pytest.raises(ValueError, match='Physical operation locked'): e.load(Stimulus())
        q = e.enqueue(Stimulus(on_s=.03)); e.run_queue([1])
        eventually(lambda: q['state'] == 'failed')
        assert 'Physical operation locked' in q['error']
        assert not any(g.running for g in e.generators.values())
    finally:
        e.close()


def test_missing_hs5_message_names_serials_and_other_programs(monkeypatch):
    from types import SimpleNamespace
    from well24.engine import missing_hs5_message
    monkeypatch.setattr('well24.engine.visible_tiepie_devices', lambda: [SimpleNamespace(name='Handyscope HS5', serial_number=42487)])
    text = missing_hs5_message({'generators': {'1': '42473', '2': '42487'}}, [1])
    assert 'HS5 1 = serial 42473' in text and 'Handyscope HS5 42487' in text and 'HS5 GUI' in text


def test_shutdown_endpoint(tmp_path):
    with TestClient(create_app(tmp_path)) as c:
        assert c.post('/api/shutdown', json={}).status_code == 404
    lifetime = BrowserLifetime(lambda: None, startup_s=60)
    with TestClient(create_app(tmp_path, browser_lifetime=lifetime)) as c:
        c.post('/api/connect', json={}).raise_for_status()
        job = c.post('/api/load', json={'on_s': 30}).json()
        c.post('/api/start', json={'channel': 1, 'entry_id': job['id']}).raise_for_status()
        r = c.post('/api/shutdown', json={})
        assert r.status_code == 400 and 'still active' in r.json()['detail']
        assert not lifetime.shutdown_requested
        c.post('/api/shutdown', json={'stop_running': True}).raise_for_status()
        eventually(lambda: lifetime.stopping)
        eventually(lambda: not c.app.state.engine.workers)
