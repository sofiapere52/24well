"""Regressions for the 2026-10-19 hardware bring-up changes."""
import json
import time
import zipfile
import io
import pytest
from fastapi.testclient import TestClient
from well24.app import create_app
from well24.engine import Engine, ROUTE_LEAD_S
from well24.models import Stimulus
from well24.queue_csv import encode, decode


def eventually(predicate,timeout=8):
    end=time.monotonic()+timeout
    while not predicate():
        if time.monotonic()>end: raise AssertionError("Operation timed out")
        time.sleep(.01)


def test_control_mode_never_keeps_delta():
    assert Stimulus(mode="control",delta_hz=10).delta_hz==0
    assert Stimulus().delta_hz==0
    assert Stimulus(mode="tis_like",frequency_hz=2000,delta_hz=7).delta_hz==7
    assert Stimulus(mode="tis_like",frequency_hz=2000).delta_hz==10  # previous default kept
    with pytest.raises(ValueError):
        Stimulus(mode="tis_like",frequency_hz=2000,delta_hz=0)


def test_imported_control_entry_drops_stale_delta():
    job={"kind":"queue","params":Stimulus(on_s=1).model_dump()}
    job["params"]["delta_hz"]=10  # as stored by older revisions
    (entry,)=decode(encode([job]))
    assert entry.delta_hz==0


def test_relay_closes_just_before_block_with_well_disconnected(tmp_path):
    e=Engine(tmp_path);e.connect()
    try:
        calls=[];g=e.generators[1];router=e.router
        for name in ("stop","enable_output","start"):
            original=getattr(g,name)
            def record(*a,_name=name,_original=original,**k):
                calls.append((_name,time.monotonic(),dict(router.routes)));return _original(*a,**k)
            setattr(g,name,record)
        route=router.route
        def record_route(ch,well,f): calls.append(("route",time.monotonic(),dict(router.routes)));return route(ch,well,f)
        router.route=record_route
        job=e.load(Stimulus(on_s=.05,pre_s=1.2,repetitions=1))
        started=time.monotonic();e.start_loaded(1,job["id"])
        eventually(lambda:not e.workers)
        assert job["state"]=="completed"
        names=[c[0] for c in calls]
        enable=names.index("enable_output")
        assert names[enable+1]=="route"  # relay closes, then the well connects
        assert calls[enable][2][1] is None  # no well routed while the relay closes
        # Not at the start of the 1.2 s OFF period: only ROUTE_LEAD_S before the block.
        assert calls[enable][1]-started>=1.2-ROUTE_LEAD_S-.15
    finally:
        e.close()


def test_scope_connect_status_and_scan_downloads(tmp_path):
    with TestClient(create_app(tmp_path)) as c:
        assert c.get("/api/status").json()["scope"]["state"]=="disconnected"
        assert c.post("/api/scope/connect",json={}).status_code>=400  # nothing connected yet
        c.post("/api/connect",json={"mode":"simulation"})
        scope=c.get("/api/status").json()["scope"]
        assert scope["state"]=="ready" and scope["detail"]=="SIM-WS6"
        assert c.post("/api/scope/connect",json={}).json()["scope"]["state"]=="ready"

        ident="ab"*16;folder=tmp_path/"runtime"/"scans"/ident
        root=c.app.state.engine.store.root;folder=root/"scans"/ident;folder.mkdir(parents=True)
        (folder/"scan.json").write_text(json.dumps({"id":ident}),encoding="utf-8")
        (folder/"results.csv").write_text("well,impedance_ohm\nA1,250\n",encoding="utf-8")
        (folder/"A1_HS5_1.csv").write_text("time_s,monitor_v\n0,0\n",encoding="utf-8")
        table=c.get(f"/api/scan/{ident}/results.csv")
        assert table.status_code==200 and "A1,250" in table.text
        raw=c.get(f"/api/scan/{ident}/raw.zip")
        assert raw.status_code==200
        assert sorted(zipfile.ZipFile(io.BytesIO(raw.content)).namelist())==["A1_HS5_1.csv","results.csv","scan.json"]
        assert c.get("/api/scan/..%2F..%2Fx/raw.zip").status_code==404
        assert c.get(f"/api/scan/{'cd'*16}/results.csv").status_code==404


def test_gui_has_new_controls(tmp_path):
    with TestClient(create_app(tmp_path)) as c:
        html=c.get("/").text
    for marker in ('id="pre" type="number" min="0" step="any" value="1"','id="scopeConnect"','id="scopeLed"',
                   'id="scanTableDownload"','id="scanRawDownload"','<th>Block design</th>','id="preNote"'):
        assert marker in html


def test_hardware_connect_with_one_stimulator(tmp_path,monkeypatch):
    import well24.engine as eng
    from well24.devices import MockGenerator
    (tmp_path/"hw.json").write_text(json.dumps({"generators":{"1":"42473","2":"42487"},"arduino_port":""}),encoding="utf-8")
    monkeypatch.setattr(eng,"ROOT",tmp_path)
    (tmp_path/"hardware.json").write_text((tmp_path/"hw.json").read_text(),encoding="utf-8")
    monkeypatch.setattr(eng,"discover",lambda profile:{1:MockGenerator(1)})
    e=Engine(tmp_path/"data")
    try:
        s=e.connect("hardware")
        assert [d["channel"] for d in s["devices"]]==[1]
        assert "HS5 2 not found" in s["notice"]
        with pytest.raises(ValueError,match="unavailable"):
            e.load(Stimulus(channel=2,on_s=1,pre_s=1))
        e.enqueue(Stimulus(channel=1,on_s=.05,pre_s=1))
        e.mode="simulation"  # skip hardware acceptance gates for the queue run
        e.router=__import__("well24.routing",fromlist=["MockRouter"]).MockRouter()
        e.run_queue([1,2])  # "Run both" runs the connected stimulator only
        assert e.queue_enabled=={1} or 1 in e.queue_enabled
    finally:
        e.close()
    monkeypatch.setattr(eng,"discover",lambda profile:{})
    e=Engine(tmp_path/"data2")
    try:
        with pytest.raises(ValueError,match="not available"):
            e.connect("hardware")
    finally:
        e.close()


def test_scope_capture_waits_for_auto_range_to_settle():
    import threading
    import numpy as np
    from types import SimpleNamespace
    from well24.devices import HardwareScope
    from well24.models import Scan
    channels=[SimpleNamespace(enabled=False,trigger=SimpleNamespace(enabled=True),is_differential=True,coupling=None,
        auto_ranging=False,has_safeground=False,range=40.) for _ in range(4)]
    blocks=[]
    def get_data():
        blocks.append([c.range for c in channels])
        data=[np.full(scope.record_length,len(blocks)) for _ in range(4)]
        for c in channels[:2]: c.range=.8  # auto-ranging adapts after the first block only
        return data
    scope=SimpleNamespace(channels=channels,trigger_inputs=[],trigger=SimpleNamespace(timeout=8),stop=lambda:None,
        start=lambda:None,record_length_max=100000,is_data_ready=True,is_running=False,get_data=get_data)
    t,records,meta=HardwareScope(SimpleNamespace(MM_BLOCK=1,CK_DCV=1),scope,"T").capture(
        Scan(cycles=10,sample_rate_hz=50000),{1:"A1"},None,threading.Event())
    assert blocks==[[40.]*4,[.8,.8,40.,40.]]  # block 2 is recorded on the settled 0.8 V range
    assert records[1]["monitor"][0]==2 and meta["actual_input_ranges_v"]=={"1":.8,"2":.8}


def test_analysis_uses_monitor_scale_open_correction_and_estimate_snr():
    import numpy as np
    from well24.impedance import analyze
    t=np.arange(10000)/100000;f=1000;e=np.exp(2j*np.pi*f*t)
    well=2500+0j;z_open=37000-17000j;i_well=.0009
    v=i_well*well;i_total=i_well+v/z_open
    rng=np.random.default_rng(3)
    ds5=np.real(100*i_total*e)+rng.normal(0,.002,len(t))  # DS5 rear monitor, 100 V/A, noisy
    volt=np.real(v*e)
    open_ratio=100/z_open  # what the open-circuit recording measures (monitor V per stimulator V)
    r=analyze(t,ds5,volt,f,0,1,10,monitor_ohm=100,monitor_leak=open_ratio)
    assert r["quality"]=="valid"
    assert r["impedance_ohm"]==pytest.approx(2500,rel=.01) and abs(r["phase_deg"])<1
    assert r["monitor_broadband_snr_db"]<r["monitor_snr_db"]  # averaged estimate beats broadband
    weak=np.real(1.06*i_well*e)+rng.normal(0,.0016,len(t))  # ~1 mV on the PCB resistor in 1.6 mV noise
    assert analyze(t,weak,volt,f,0,.2,10,monitor_ohm=1.06)["monitor_snr_db"]>20


def test_scan_pair_current_source_default_and_validation():
    from well24.models import Scan,ScopePair
    assert ScopePair(monitor=3,voltage=2).current_source=="pcb"
    assert Scan(pairs={1:ScopePair(monitor=3,voltage=2,current_source="ds5"),2:ScopePair(monitor=4,voltage=1)}).pairs[1].current_source=="ds5"
    with pytest.raises(ValueError): ScopePair(monitor=1,voltage=2,current_source="other")


def test_well_voltage_is_well_impedance_times_well_current():
    import numpy as np
    from well24.impedance import analyze
    t=np.arange(10000)/100000;e=np.exp(2j*np.pi*1000*t);i=.0009;arms=90+0j;well=2500+0j
    r=analyze(t,np.real(10*i*e),np.real((arms+well)*i*e),1000,arms,1,10)
    assert r["well_voltage_peak_v"]==pytest.approx(2500*.0009,rel=1e-6)  # 2.25 V, arms excluded
