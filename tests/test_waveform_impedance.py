import numpy as np
import pytest
from well24.models import Stimulus, Scan, ScopePair
from well24.waveform import build, plan, samples, preview
from well24.impedance import Calibration, analyze


@pytest.mark.parametrize("shape",["sine","square","triangle","ramp"])
def test_control_peak_and_on_only(shape):
    p=Stimulus(shape=shape,on_s=.1,pre_s=10,post_s=20,repetitions=100,ramp_s=.01)
    info=plan(p);y=build(p)
    assert len(y)==info["samples"]
    assert len(y)<10000
    assert max(abs(y))<=1
    assert y[0]==y[-1]==0


def test_partial_cycle_not_renormalized():
    p=Stimulus(frequency_hz=1,on_s=.01)
    y=build(p)
    assert max(abs(y))<.1


def test_tis_components_and_ramp():
    p=Stimulus(mode="tis_like",frequency_hz=2000,delta_hz=10,on_s=.1)
    info=plan(p);y=build(p);t=np.arange(len(y))/info["sample_rate_hz"]
    assert np.allclose(y,.5*(np.cos(2*np.pi*2000*t)-np.cos(2*np.pi*2010*t)),atol=1e-7)
    assert np.max(abs(y))<=1


def test_preview_pair_separates_wells():
    p=Stimulus(wells=["A1","B2"],on_s=.2,pre_s=.1,post_s=.3)
    a=preview(p,"A1");b=preview(p,"B2")
    assert np.count_nonzero(np.array(a["current_ma"])*np.array(b["current_ma"]))==0


@pytest.mark.parametrize("changes",[{"wells":["A9"]},{"wells":["A1","A1"]},{"on_s":1,"ramp_s":.6},
    {"frequency_hz":float("nan")},{"trigger_in":True},{"pulse_width_s":1}])
def test_invalid_parameters(changes):
    with pytest.raises(ValueError): Stimulus(**changes)


def test_filter_and_capacity():
    assert not Stimulus(frequency_hz=1000).filter_on
    assert Stimulus(frequency_hz=1001).filter_on
    assert Stimulus(mode="tis_like").filter_on
    assert not Stimulus(mode="tis_like",filter_on=False).filter_on
    with pytest.raises(ValueError): plan(Stimulus(on_s=3600,frequency_hz=100000))


def test_calibration_sign_and_no_extrapolation():
    c=Calibration()
    assert c.arms(100,True).imag < -2000
    assert abs(c.arms(100,False).imag)<1
    assert 90<abs(c.arms(100,False))<100
    with pytest.raises(ValueError): c.value("pt",.1)


def test_estimate_parallel_path_once():
    c=Calibration();p=Stimulus(frequency_hz=1000,filter_on=True)
    branch=c.arms(1000,True)+c.value("pt",1000)
    out=c.estimate(p)
    assert out["circuit_ohm"]==pytest.approx(abs(100000*branch/(100000+branch)))
    assert out["well_voltage_peak_v"]==pytest.approx(abs(.001*100000/(100000+branch)*c.value("pt",1000)))


def test_known_rc_and_pcb_compensation():
    t=np.arange(10000)/100000;f=1000;current=.0001*np.exp(.3j)
    arms=90-300j;well=150-40j
    monitor=np.real(10*current*np.exp(2j*np.pi*f*t))
    voltage=np.real((arms+well)*current*np.exp(2j*np.pi*f*t))
    r=analyze(t,monitor,voltage,f,arms,.2,2)
    assert r["quality"]=="valid"
    assert r["resistance_ohm"]==pytest.approx(150)
    assert r["reactance_ohm"]==pytest.approx(-40)


@pytest.mark.parametrize("fault",["clipped","no_current","noise","drift","missing"])
def test_measurement_quality(fault):
    t=np.arange(10000)/100000;i=.001*np.cos(2*np.pi*1000*t);v=i*20
    if fault=="clipped": v*=100
    if fault=="no_current": i*=0
    if fault=="noise": i+=np.random.default_rng(1).normal(0,.01,len(t))
    if fault=="drift": v[len(v)//2:]*=2
    if fault=="missing": v[1]=np.nan
    out=analyze(t,i,v,1000,0,.2,2)
    assert out["quality"]=="invalid"
    assert out["impedance_ohm"] is None


def test_scan_mapping_collision():
    with pytest.raises(ValueError): Scan(pairs={1:ScopePair(monitor=1,voltage=1),2:ScopePair(monitor=3,voltage=4)})
