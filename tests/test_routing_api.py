import re
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from well24.models import WELLS
from well24.routing import address,MockRouter,RoutingFault
from well24.app import create_app


@pytest.mark.parametrize("channel",[1,2])
@pytest.mark.parametrize("well",WELLS)
def test_mapping_against_original_arduino(channel,well):
    root=Path(__file__).resolve().parents[1]
    text=(root/"resources/PCB_code/IDE_031225/dms283-mux-Wellplate-v1/dms283-mux-Wellplate-v1.ino").read_text()
    section=text.split(f"void IN{channel}(")[1].split("void ")[0]
    block=re.search(r'if \(WELL == "'+well+r'"\) \{(.*?)\n  \}',section,re.S).group(1)
    bank,addr=address(well)
    for bit in range(4 if bank==0 else 3):
        expected="HIGH" if addr&(1<<bit) else "LOW"
        assert f"digitalWrite(MUX{channel}_{bank+1}_A{bit}, {expected})" in block
    assert f"digitalWrite(MUX{channel}_{bank+1}_EN, HIGH)" in block


@pytest.mark.parametrize("well",WELLS)
@pytest.mark.parametrize("filter_on",[False,True])
def test_routing_conflict_and_filter(well,filter_on):
    r=MockRouter();r.route(1,well,filter_on)
    with pytest.raises(RoutingFault):r.route(2,well,filter_on)
    assert r.routes[1]==well
    r.disconnect(1);r.route(2,well,filter_on)
    assert r.filters[2]==filter_on


def test_api_offline_assets_validation_and_origin(tmp_path):
    with TestClient(create_app(tmp_path)) as c:
        assert c.get('/').status_code==200
        html=c.get('/').text
        assert 'cdn.' not in html and 'https://' not in html
        assert c.post('/api/connect',json={}).json()['mode']=='simulation'
        assert c.post('/api/load',json={'wells':['Z9']}).status_code==422
        assert c.post('/api/connect',json={},headers={'Origin':'https://other.example'}).status_code==403
        assert c.get('/api/files/../../hardware.json').status_code!=200
        r=c.post('/api/estimate',json={'frequency_hz':1000})
        assert r.status_code==200
        assert r.json()['well_voltage_peak_v']>0
