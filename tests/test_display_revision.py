import re
import time
import numpy as np
from fastapi.testclient import TestClient
from well24.app import create_app
from well24.models import Stimulus
from well24.waveform import preview, samples
from well24.impedance import Calibration


def test_prediction_field_9mm():
    e=Calibration().estimate(Stimulus())
    assert e['electrode_distance_m']==.009
    assert e['well_field_peak_v_per_m']==e['well_voltage_peak_v']/.009


def test_open_existing_record_and_unique_export(monkeypatch,tmp_path):
    opened=[]
    monkeypatch.setattr('well24.app.os.startfile',lambda p:opened.append(p))
    with TestClient(create_app(tmp_path)) as c:
        c.post('/api/queue',json=Stimulus().model_dump()).raise_for_status()
        name=c.get('/api/files').json()[0]
        c.post('/api/files/open',json={'name':name}).raise_for_status()
        assert opened==[str((tmp_path/name).resolve())]
        assert c.post('/api/files/open',json={'name':'../secret.csv'}).status_code==404
        assert c.post('/api/files/open',json={'name':'queue.sqlite'}).status_code==404
        assert c.get('/api/files/'+name).status_code==404
        headers=[c.get('/api/queue/export').headers['content-disposition'] for _ in range(2)]
        assert headers[0]!=headers[1]
        assert re.search(r'queue_exp_\d{8}_\d{6}_\d{6}_[a-f0-9]{8}\.csv',headers[0])


def test_overview_has_carrier_extrema_and_zoom_has_buffer_samples():
    p=Stimulus(frequency_hz=1000,on_s=10,amplitude_ma=.4)
    out=preview(p)
    assert out['representation']=='minmax_envelope'
    y=np.asarray(out['current_ma'])
    # Each 5 ms display bucket contains complete cycles; no false beat pattern.
    assert np.all(y[::2]<-.399) and np.all(y[1::2]>.399)
    zoom=preview(p,start=1.001,end=1.003)
    assert zoom['representation']=='samples'
    expected=samples(p,np.floor(np.asarray(zoom['time'])*zoom['sample_rate_hz']),zoom['sample_rate_hz'])*.4
    assert np.allclose(zoom['current_ma'],expected)


def test_tis_overview_bounds_preserve_ramp_and_beats():
    p=Stimulus(mode='tis_like',frequency_hz=2000,delta_hz=10,on_s=2,ramp_s=.1)
    out=preview(p);y=np.asarray(out['current_ma'])
    assert out['representation']=='minmax_envelope'
    assert np.max(abs(y))<=1 and np.max(abs(y[:10]))<.1
    assert max(y)>.99
    assert set(out['currents_by_well'])=={'A1'}


def test_d5_enqueue_needs_no_load_and_records_automatic_load(tmp_path):
    with TestClient(create_app(tmp_path)) as c:
        c.post('/api/connect',json={'mode':'simulation'}).raise_for_status()
        entry=c.post('/api/queue',json=Stimulus(wells=['D5'],on_s=.03).model_dump()).json()
        assert entry['state']=='queued'
        assert c.get('/api/status').json()['loaded']=={}
        c.post('/api/queue/run',json={'channels':[1]}).raise_for_status()
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            j=c.get('/api/status').json()['jobs'][0]
            if j['state'] in ('completed','failed'):break
            time.sleep(.01)
        assert j['state']=='completed'
        assert j['loaded_at']<=j['started_at']<=j['ended_at']
        events=c.get('/api/status').json()['events']
        assert any(e['state']=='load_completed' for e in events)
