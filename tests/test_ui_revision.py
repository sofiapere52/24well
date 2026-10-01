import threading
import hashlib
import time
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from fastapi.testclient import TestClient
from well24.app import create_app
from well24.engine import Engine
from well24.models import Stimulus,Scan
from well24.queue_summary import summarize
from well24.devices import HardwareScope
from well24.waveform import preview


def job(ch,wells,on=10,reps=1,**kwargs):
    return {'id':str(ch)+str(wells),'kind':'queue','state':'queued','completed_blocks':[],
            'params':Stimulus(channel=ch,wells=wells,on_s=on,repetitions=reps,**kwargs).model_dump()}


def test_queue_concurrency_and_shared_well():
    a=job(1,['A1']);b=job(2,['B1'],on=20)
    assert summarize([a,b])['estimated_seconds']==20
    b['params']['wells']=['A1']
    q=summarize([a,b]);assert q['estimated_seconds']==30 and q['unique_wells']==1
    assert q['per_well_protocol_s']=={'A1':30}


def test_queue_pair_fifo_and_counts():
    a=job(1,['A1','B1'],on=10,reps=2,pre_s=2,post_s=3)
    b=job(2,['B1'],on=5);c=job(2,['C1'],on=5)
    q=summarize([a,b,c])
    assert q['estimated_seconds']==60
    assert q['unique_wells']==3 and q['well_blocks']==6
    assert q['per_well_protocol_s']=={'A1':50,'B1':55,'C1':5}


def test_queue_active_remaining_and_history():
    a=job(1,['A1'],on=10,reps=2);a['state']='running';a['completed_blocks']=[{}]
    b=job(2,['A2']);b['state']='completed'
    q=summarize([a,b],{a['id']:12})
    assert q['estimated_seconds']==8 and q['well_blocks']==1 and q['unique_wells']==1


def test_preview_zoom_beyond_four_repetitions():
    p=Stimulus(on_s=1,repetitions=100)
    assert preview(p)['time'][-1]==100
    zoom=preview(p,start=50,end=50.01)
    assert zoom['time'][0]==50 and zoom['time'][-1]==50.01


def test_scan_preserves_different_filters_and_leds(tmp_path):
    e=Engine(tmp_path);e.connect()
    try:
        e.router.route(1,'A1',True);e.router.route(2,'C1',False);e.router.disconnect()
        state=e.start_scan(Scan(wiring_confirmed=True,cycles=10,settling_s=0,filter_on=False))
        end=time.monotonic()+10
        while e.scan_worker and time.monotonic()<end:time.sleep(.01)
        assert state['state']=='completed',state.get('error')
        assert state['settings']['channel_filters']=={'1':True,'2':False}
        for r in state['results']:
            assert r['filter_on']==(r['channel']==1)
            assert r['impedance_ohm']==pytest.approx(abs(e.cal.value('pt',1000)),rel=.001)
        assert e.router.filters=={1:True,2:False}
        e.load(Stimulus());assert e.status()['devices'][0]['state']=='armed'
        e.stop();assert e.status()['devices'][0]['state']=='ready'
    finally:e.close()


def test_unknown_filter_blocks_scan(tmp_path):
    e=Engine(tmp_path);e.connect();e.router.failed=True
    try:
        with pytest.raises(RuntimeError,match='unknown'):e.start_scan(Scan(wiring_confirmed=True))
        assert not e.scan_worker and e.error
    finally:e.close()


def test_scope_automatic_range_and_normal_polarity():
    channels=[SimpleNamespace(enabled=False,trigger=SimpleNamespace(enabled=True),is_differential=True,
        coupling=None,auto_ranging=False,has_safeground=True,safeground_enabled=True,range=.2+i) for i in range(4)]
    scope=SimpleNamespace(channels=channels,trigger_inputs=[],trigger=SimpleNamespace(timeout=8),
        stop=lambda:None,start=lambda:None,record_length_max=100000,is_data_ready=True)
    scope.get_data=lambda:[np.sin(2*np.pi*np.arange(scope.record_length)/50) for _ in range(4)]
    adapter=HardwareScope(SimpleNamespace(MM_BLOCK=1,CK_DCV=1),scope,'TEST')
    s=Scan(cycles=10,sample_rate_hz=50000)
    t,records,meta=adapter.capture(s,{1:'A1',2:'C1'},None,threading.Event())
    assert all(c.auto_ranging and not c.safeground_enabled for c in channels)
    assert meta['actual_input_ranges_v']=={'1':.2,'2':1.2,'3':2.2,'4':3.2}
    assert meta['polarity']=='normal' and scope.trigger.timeout==0
    assert records[1]['monitor'][1]>0 and len(t)==500


def test_api_hidden_scan_defaults_and_local_plot(monkeypatch,tmp_path):
    monkeypatch.setattr(Engine,'start_scan',lambda self,s:s.model_dump())
    with TestClient(create_app(tmp_path)) as c:
        out=c.post('/api/scan/start',json={'settling_s':4,'cycles':10}).json()
        assert out['settling_s']==.2 and out['cycles']==100
        html=c.get('/').text
        assert 'cdn.jsdelivr' not in html and 'id="scanFilter"' not in html and 'id="settle"' not in html
        assert c.get('/vendor/uPlot.iife.min.js').status_code==200
        assert c.get('/preview.js').status_code==200


def test_hs5_gesture_code_reused_exactly():
    # SHA-256 of the reviewed HS5 sections, with universal-newline normalization.
    # This provenance check must also run from a standalone clone.
    root=Path(__file__).resolve().parents[1]
    new=(root/'static/preview.js').read_text(encoding='utf-8')
    sections = [
        ('function onPreviewWheelCapture', 1405, 'b30f5c8ac84da496b3131a09b7ad8722d3f3484404478b8dd6357b923a8f4428'),
        ('function makeZoomPanPlugin', 2393, 'ac9be244a400ca8fc3a6248db18f914348195ce3d728ec2a0885487bb4855e3a'),
    ]
    for start, length, expected in sections:
        section = new[new.index(start):new.index(start)+length]
        assert hashlib.sha256(section.encode()).hexdigest() == expected
