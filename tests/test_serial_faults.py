import threading
import pytest
from well24.routing import SerialRouter,MockRouter,RoutingFault
from well24.models import WELLS


class FakeSerial:
    def __init__(self,replies): self.replies=list(replies);self.writes=[]
    def write(self,data): self.writes.append(data)
    def readline(self): return self.replies.pop(0) if self.replies else b''


def router(replies):
    r=SerialRouter.__new__(SerialRouter)
    MockRouter.__init__(r)
    r.sequence=0;r.serial=FakeSerial(replies)
    return r


def test_correlated_reply_ignores_old_id():
    r=router([b'88 OK ROUTE 1 1 B1\n',b'1 OK ROUTE 1 0 A1\n'])
    r.route(1,'A1',True)
    assert r.routes[1]=='A1' and r.filters[1]
    assert r.serial.writes==[b'1 ROUTE 1 0 A1\n']


@pytest.mark.parametrize('reply',[b'1 OK ROUTE 1 1 A1\n',b'1 ERR INVALID_COMMAND\n',b'BOOT V2 DISCONNECTED\n',b'0 ERR WATCHDOG\n'])
def test_uncertain_reply_latches_failure(reply):
    r=router([reply])
    with pytest.raises(RoutingFault): r.route(1,'A1',True)
    assert r.routes[1] is None and r.failed
    with pytest.raises(RoutingFault): r.command('PING')


@pytest.mark.parametrize('reply',[b'',b'garbled\n',b'7 OK ROUTE 1 0 A1\n'])
def test_missing_matching_ack_times_out(monkeypatch,reply):
    ticks=iter([0,.1,2])
    monkeypatch.setattr('well24.routing.time.monotonic',lambda:next(ticks))
    r=router([reply])
    with pytest.raises(RoutingFault,match='timeout'): r.route(1,'A1',True)
    assert r.failed


def test_all_dual_route_combinations():
    for first in WELLS:
        for second in WELLS:
            for a in (False,True):
                for b in (False,True):
                    r=MockRouter();r.route(1,first,a)
                    if first==second:
                        with pytest.raises(RoutingFault):r.route(2,second,b)
                        assert r.routes[2] is None
                    else:
                        r.route(2,second,b)
                        assert r.routes=={1:first,2:second}
                    assert r.routes[1]==first


@pytest.mark.parametrize('well',['','A0','A7','A10','E1','a1','0','A1 extra','A1\x00'])
def test_malformed_well_never_sent(well):
    r=router([])
    with pytest.raises(ValueError):r.route(1,well,True)
    assert r.serial.writes==[]
