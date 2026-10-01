"""Single-owner instrument adapters based on HS5 and WD6 block acquisition flows.

Hardware operations require an explicit accepted profile; no device is opened on import.
"""
from array import array
from functools import wraps
import threading
import time
import numpy as np
from . import waveform


def wait(cancel, seconds):
    if cancel.wait(max(0, seconds)):
        raise InterruptedError("Operator stop")


def instrument_lock(method):
    @wraps(method)
    def locked(self,*args,**kwargs):
        with self.lock: return method(self,*args,**kwargs)
    return locked


class MockGenerator:
    def __init__(self, channel):
        self.serial=f"SIM-HS5-{channel}"
        self.running=False
        self.params=None
        self.info=None
        self.buffer=None

    def load(self, p):
        self.info=waveform.plan(p)
        self.buffer=waveform.build(p)
        self.params=p
        return {**self.info,"serial":self.serial,"amplitude_v":p.amplitude_ma}

    def primer(self, p, cancel):
        # Simulation explicitly represents a received trigger; never claims external hardware.
        wait(cancel,.005)
        return time.monotonic()

    def start(self, continuous=False):
        self.running=True
        self.started=time.monotonic()

    def done(self):
        return time.monotonic()-self.started >= self.info["actual_on_s"]

    def stop(self):
        self.running=False

    def close(self):
        self.stop()


class HardwareGenerator:
    def __init__(self, lt, gen, serial):
        self.lt,self.gen,self.serial=lt,gen,serial
        self.params=None
        self.info=None
        self.lock=threading.RLock()
        self.stop()
        self._clear_triggers()

    def _trigger(self, number, direction):
        collection=getattr(self.gen,f"trigger_{direction}s")
        for obj in collection:
            if f"EXT {number}".lower() in obj.name.lower():
                return obj
        raise RuntimeError(f"EXT {number} {direction} unavailable")

    def _clear_triggers(self):
        for collection in (self.gen.trigger_inputs,self.gen.trigger_outputs):
            for obj in collection:
                obj.enabled=False

    @instrument_lock
    def load(self,p):
        self.stop()
        self._clear_triggers()
        g,lt=self.gen,self.lt
        g.signal_type=lt.ST_ARBITRARY
        g.frequency_mode=lt.FM_SAMPLERATE
        cap=int(g.data_length_max)
        info=waveform.plan(p,cap,float(g.frequency_max))
        g.frequency=info["sample_rate_hz"]
        rate=float(g.frequency)
        values=waveform.build(p,rate,cap)
        g.amplitude=p.amplitude_ma # accepted DS5 profile: 1 mA/V
        g.offset=0
        if abs(float(g.amplitude)-p.amplitude_ma)>max(1e-5,p.amplitude_ma*.001):
            raise RuntimeError("Generator amplitude readback differs from requested value")
        g.set_data(array("f",values))
        g.mode=lt.GM_BURST_COUNT
        g.burst_count=1
        if int(g.burst_count)!=1 or g.mode!=lt.GM_BURST_COUNT:
            raise RuntimeError("Finite hardware burst could not be established")
        if p.trigger_stim:
            out=self._trigger(3,"output")
            out.event=lt.TOE_GENERATOR_STOP
            out.enabled=True
        self.params=p
        self.info={**info,"sample_rate_hz":rate,"samples":len(values),"actual_on_s":len(values)/rate,
                   "duration_quantization_s":len(values)/rate-p.on_s,"serial":self.serial,
                   "amplitude_v":float(g.amplitude)}
        return self.info

    def primer(self,p,cancel):
        # Zero data, routes disconnected by engine. Trigger pin behavior requires bench acceptance.
        g,lt=self.gen,self.lt
        self.stop();self._clear_triggers()
        g.set_data(array("f",np.zeros(max(8,round(.005*self.info["sample_rate_hz"])),dtype=np.float32)))
        if p.trigger_out:
            out=self._trigger(1,"output");out.event=lt.TOE_GENERATOR_STOP;out.enabled=True
        if p.trigger_in:
            inp=self._trigger(2,"input");inp.kind=lt.TK_RISINGEDGE;inp.enabled=True
        g.output_enable=True;g.start()
        deadline=time.monotonic()+p.trigger_timeout_s
        while not g.is_running:
            if time.monotonic()>deadline:
                raise RuntimeError("Trigger wait timed out")
            wait(cancel,.001)
        edge=time.monotonic()
        while g.is_burst_active:
            if time.monotonic()-edge>.1: raise RuntimeError("Zero-output trigger primer did not finish")
            wait(cancel,.001)
        edge=time.monotonic() # Host observation of primer stop; requires bench verification.
        self.stop()
        return edge

    @instrument_lock
    def start(self,continuous=False):
        if continuous:
            self.gen.mode=self.lt.GM_CONTINUOUS
        self.gen.output_enable=True
        self.gen.start()

    @instrument_lock
    def done(self):
        return not self.gen.is_burst_active

    @instrument_lock
    def stop(self):
        # Attempt both operations; preserve failures instead of claiming output stopped.
        failures=[]
        for operation in (self.gen.stop,lambda:setattr(self.gen,"output_enable",False)):
            try: operation()
            except Exception as exc: failures.append(str(exc))
        if failures: raise RuntimeError("Unable to confirm output stop: "+"; ".join(failures))

    def close(self):
        self.stop()
        self.gen=None


class MockScope:
    def capture(self,scan,assignments,calibration,cancel):
        rate=scan.sample_rate_hz
        n=round(scan.cycles/scan.frequency_hz*rate)
        if n>2_000_000: raise ValueError("Scan record too large")
        wait(cancel,n/rate)
        t=np.arange(n)/rate
        data={}
        rng=np.random.default_rng(24)
        for ch,well in assignments.items():
            z=calibration.arms(scan.frequency_hz,scan.channel_filters.get(ch,False))+calibration.value("pt",scan.frequency_hz)
            source_i=scan.amplitude_ma/1000
            branch_i=source_i*100000/(100000+z)
            v=branch_i*z
            pair=scan.pairs[ch]
            data[ch]={"monitor":np.real(branch_i*10*np.exp(2j*np.pi*scan.frequency_hz*t))+rng.normal(0,1e-7,n),
                      "voltage":np.real(v*np.exp(2j*np.pi*scan.frequency_hz*t))+rng.normal(0,1e-7,n),
                      "monitor_limit":max(.2*pair.monitor_scale,abs(branch_i)*10*1.5),
                      "voltage_limit":max(.2*pair.voltage_scale,abs(v)*1.5)}
        return t,data,{"serial":"SIM-WS6","sample_rate_hz":rate,"samples":n,"simulation":True,"auto_range":True,"polarity":"normal",
                       "actual_input_ranges_v":{str(getattr(scan.pairs[ch],signal)):data[ch][signal+"_limit"]/getattr(scan.pairs[ch],signal+"_scale") for ch in assignments for signal in ("monitor","voltage")}}

    def close(self): pass


class HardwareScope:
    def __init__(self,lt,scope,serial):
        self.lt,self.scope,self.serial=lt,scope,serial

    def capture(self,scan,assignments,calibration,cancel):
        s,lt=self.scope,self.lt
        s.stop();s.measure_mode=lt.MM_BLOCK
        used={}
        for stim in assignments:
            pair=scan.pairs[stim]
            used[pair.monitor-1]=pair.monitor_scale
            used[pair.voltage-1]=pair.voltage_scale
        if max(used)>=len(s.channels): raise RuntimeError("Scope does not have required inputs")
        for i,ch in enumerate(s.channels):
            ch.enabled=i in used
            ch.trigger.enabled=False
            if i in used:
                if not ch.is_differential: raise RuntimeError("Scan requires differential scope inputs")
                ch.coupling=lt.CK_DCV
                ch.auto_ranging=True
                if not ch.auto_ranging: raise RuntimeError("Automatic scope ranging unavailable")
                if ch.has_safeground:
                    ch.safeground_enabled=False
                    if ch.safeground_enabled: raise RuntimeError("Cannot disable SafeGround")
        for trig in s.trigger_inputs: trig.enabled=False
        s.sample_rate=scan.sample_rate_hz
        rate=float(s.sample_rate)
        if rate<50*scan.frequency_hz: raise RuntimeError("Scope sample rate below fidelity threshold")
        n=round(scan.cycles/scan.frequency_hz*rate)
        if n>int(s.record_length_max): raise RuntimeError("Acquisition must fit in one simultaneous scope block")
        s.record_length=n
        if int(s.record_length)!=n: raise RuntimeError("Scope changed requested record length")
        s.pre_sample_ratio=0
        s.trigger.timeout=0
        s.start()
        deadline=time.monotonic()+n/rate+10
        try:
            while not s.is_data_ready:
                if time.monotonic()>deadline: raise RuntimeError("Scope acquisition timed out")
                wait(cancel,.005)
            raw=s.get_data()
        finally:
            s.stop()
        if any(len(raw[i])!=n for i in used): raise RuntimeError("Incomplete simultaneous acquisition")
        t=np.arange(n)/rate
        data={}
        for ch in assignments:
            p=scan.pairs[ch]
            data[ch]={"monitor":np.asarray(raw[p.monitor-1])*p.monitor_scale,
                      "voltage":np.asarray(raw[p.voltage-1])*p.voltage_scale,
                      "monitor_limit":float(s.channels[p.monitor-1].range)*p.monitor_scale,
                      "voltage_limit":float(s.channels[p.voltage-1].range)*p.voltage_scale}
        return t,data,{"serial":self.serial,"sample_rate_hz":rate,"samples":n,"simulation":False,
                       "auto_range":True,"polarity":"normal",
                       "actual_input_ranges_v":{str(i+1):float(s.channels[i].range) for i in used}}

    def close(self):
        self.scope.stop();self.scope=None


def discover(profile):
    import libtiepie as lt
    lt.network.auto_detect_enabled=False # USB only; no internet or network discovery.
    lt.device_list.update()
    found={}
    wanted={str(ch):str(serial) for ch,serial in profile.get("generators",{}).items() if serial}
    if any(ch not in ("1","2") for ch in wanted) or len(set(wanted.values()))!=len(wanted):
        raise ValueError("Configure distinct serial numbers for HS5 1 and HS5 2")
    try:
        for item in lt.device_list:
            for channel,serial in wanted.items():
                if str(item.serial_number)==serial and item.can_open(lt.DEVICETYPE_GENERATOR):
                    if "HS5" not in str(item.name).upper(): raise ValueError("Configured generator is not a TiePie HS5")
                    gen=item.open_generator()
                    found[int(channel)]=HardwareGenerator(lt,gen,serial)
                    found[int(channel)].name=str(item.name)
    except Exception:
        for g in found.values():
            try: g.close()
            except Exception: pass
        raise
    return found


def open_scope(profile):
    import libtiepie as lt
    serial=profile.get("scope_serial")
    if not serial: raise RuntimeError("Scope serial number must be explicitly configured")
    lt.device_list.update()
    for item in lt.device_list:
        if str(item.serial_number)==str(serial) and item.can_open(lt.DEVICETYPE_OSCILLOSCOPE):
            scope=item.open_oscilloscope()
            if not scope.measure_modes & lt.MM_BLOCK:
                raise RuntimeError("Block acquisition unavailable")
            return HardwareScope(lt,scope,str(serial))
    raise RuntimeError("Configured WS6 unavailable or already owned by another application")
