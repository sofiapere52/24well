import csv
import io
import pytest
from fastapi.testclient import TestClient
from well24.app import create_app
from well24.engine import Engine
from well24.models import Stimulus
from well24.queue_csv import encode, decode


def templates():
    return [Stimulus(channel=2,wells=['D6','A1'],mode='tis_like',frequency_hz=2000,delta_hz=13,
                     amplitude_ma=.12,on_s=12,ramp_s=.5,pre_s=.2,post_s=3,repetitions=7,
                     filter_on=False,trigger_in=True,trigger_out=True,trigger_stim=True,trigger_timeout_s=61),
            Stimulus(shape='square',pulse_width_s=.001,channel=1,wells=['C3'])]


def export(ps):
    return encode([{'kind':'queue','params':p.model_dump()} for p in ps])


def test_exact_editable_roundtrip():
    ps=templates()
    assert decode(export(ps))==ps
    text=export(ps).replace('D6;A1','B2;C4')
    assert decode(text)[0].wells==['B2','C4']


@pytest.mark.parametrize('change',[
    lambda s:s.replace('D6;A1','Z1;A1'),
    lambda s:s.replace('False','perhaps',1),
    lambda s:s.replace('format_version','unknown'),
    lambda s:s+'1,2\n',
    lambda s:s.replace('2000.0','NaN'),
])
def test_invalid_import_no_partial_change(tmp_path,change):
    with TestClient(create_app(tmp_path)) as c:
        c.post('/api/queue',json=Stimulus().model_dump()).raise_for_status()
        before=c.get('/api/status').json()['jobs']
        r=c.post('/api/queue/import',json={'csv':change(export(templates()))})
        assert r.status_code==400,r.text
        assert c.get('/api/status').json()['jobs']==before


def test_reset_import_and_restart(tmp_path):
    with TestClient(create_app(tmp_path)) as c:
        for p in templates():c.post('/api/queue',json=p.model_dump()).raise_for_status()
        saved=c.get('/api/queue/export')
        assert 'attachment' in saved.headers['content-disposition']
        c.post('/api/queue/reset').raise_for_status()
        state=c.get('/api/status').json()
        assert state['jobs']==[] and state['queue_summary']['unique_wells']==0
        assert all(j['archived'] for j in c.app.state.engine.store.jobs())
    with TestClient(create_app(tmp_path)) as c:
        assert c.get('/api/status').json()['jobs']==[]
        c.post('/api/queue/import',json={'csv':saved.text}).raise_for_status()
        state=c.get('/api/status').json()
        assert [j['params'] for j in state['jobs']]==[p.model_dump() for p in templates()]
        assert all(j['state']=='queued' and not j['started_at'] for j in state['jobs'])
        assert state['queue_enabled']==[]
        assert decode(c.get('/api/queue/export').text)==templates()
        assert list(tmp_path.glob('events_*.csv'))


def test_queue_edit_rejected_while_loaded(tmp_path):
    e=Engine(tmp_path);e.connect()
    try:
        e.load(Stimulus())
        before=e.status()['jobs']
        with pytest.raises(ValueError):e.reset_queue()
        with pytest.raises(ValueError):e.import_queue(templates())
        assert e.status()['jobs']==before
    finally:e.close()


def test_import_transaction_rollback(tmp_path):
    e=Engine(tmp_path)
    try:
        e.store.db.execute("CREATE TRIGGER reject_second BEFORE INSERT ON jobs WHEN (SELECT COUNT(*) FROM jobs)>0 BEGIN SELECT RAISE(ABORT, 'test write failure'); END")
        with pytest.raises(Exception,match='test write failure'):e.import_queue(templates())
        assert e.jobs==[] and e.store.jobs()==[] and e.store.recent()==[]
    finally:e.close()
