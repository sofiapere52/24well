import csv
import json
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
import numpy as np
from .models import Stimulus, Scan, WELLS
from .queue_summary import summarize
from .store import Store, now, replace_file
from .power import KeepAwake
from .routing import MockRouter, SerialRouter, RoutingFault
from .devices import MockGenerator, MockScope, discover, open_scope, wait
from .impedance import Calibration, analyze, ROOT

ACTIVE = {"loading","waiting_trigger","running"}


class Engine:
    def __init__(self, data_dir=None):
        self.lock=threading.RLock()
        self.store=Store(data_dir or ROOT/"data"/"runtime")
        self.cal=Calibration()
        self.jobs=self.store.jobs()
        for job in self.jobs:
            if job["state"] in ACTIVE or job["state"]=="loaded":
                job["state"]="interrupted";job["ended_at"]=now()
                self.store.save(job)
                self.store.event(job["id"],"interrupted",{"reason":"application_restart","params":job["params"]})
        self.store.repair_exports()
        self.mode="disconnected";self.profile={};self.generators={};self.router=None;self.scope=None
        self.loaded={};self.reserved={};self.workers={};self.queue_enabled=set()
        self.scan_state=None;self.scan_worker=None
        for path in sorted((self.store.root/"scans").glob("*/scan.json")):
            state=json.loads(path.read_text(encoding="utf-8"))
            if state["state"]=="running":
                state.update(state="interrupted",ended_at=now(),error="Application restarted; scan was not resumed")
                self._save_scan(path.parent,state)
            # Scan folder names are random UUIDs, not chronological identifiers.
            stamp = datetime.fromisoformat(state['started_at']).timestamp() if state.get('started_at') else float('-inf')
            previous = self.scan_state
            previous_stamp = datetime.fromisoformat(previous['started_at']).timestamp() if previous and previous.get('started_at') else float('-inf')
            if previous is None or stamp >= previous_stamp:
                self.scan_state=state
        self.power=KeepAwake();self.error=None;self.shutdown=threading.Event()
        self.manual_awake=False;self.run_clocks={}
        self.dispatcher=threading.Thread(target=self._dispatch,daemon=True);self.dispatcher.start()

    def event(self,job,state,**details):
        with self.lock:
            job["state"]=state
            self.store.save(job)
            self.store.event(job["id"],state,{"params":job["params"],"simulation":job["simulation"],"completed_repetitions":job.get("completed_repetitions",0),**details})

    def _gate(self,p=None,scan=False):
        if self.mode=="simulation": return
        required=["hardware_accepted","routing_verified","limits_verified","calibration_accepted","topology_verified"]
        if scan: required += ["scan_accepted","differential_wiring_verified","scan_current_validated"]
        if p and (p.trigger_in or p.trigger_out or p.trigger_stim): required += ["triggers_verified"]
        if p and len(p.wells)==2: required += ["well_switching_verified"]
        if any(self.profile.get(k) is not True for k in required) or not self.profile.get("acceptance_record"):
            raise ValueError("Physical operation locked: complete the bench acceptance record and hardware profile first")
        for name in ("min_frequency_hz","max_frequency_hz","max_current_ma","max_output_peak_v"):
            if not isinstance(self.profile.get(name),(int,float)) or not np.isfinite(self.profile[name]) or self.profile[name]<=0:
                raise ValueError(f"Hardware profile requires a verified positive {name}")
        if p:
            highest=p.frequency_hz+(p.delta_hz if p.mode=="tis_like" else 0)
            if not self.profile["min_frequency_hz"]<=p.frequency_hz<=highest<=self.profile["max_frequency_hz"]:
                raise ValueError("Frequency outside accepted hardware range")
            if p.amplitude_ma>self.profile["max_current_ma"]:
                raise ValueError("Current exceeds accepted limit")
            if p.shape!="sine":
                if not self.profile.get("nonsinusoidal_verified"):
                    raise ValueError("Harmonic/transient voltage limits require separate bench acceptance")
            if self.cal.estimate(p)["required_output_peak_v"]>self.profile["max_output_peak_v"]:
                raise ValueError("Estimated output voltage exceeds accepted PCB operating limit")

    def connect(self,mode="simulation",channels=(1,2)):
        with self.lock:
            if self.workers or self.scan_worker or self.loaded:
                raise ValueError("Stop active operations and unload before reconnecting")
            self.queue_enabled.clear()
            self._close_devices()
            if mode=="simulation":
                self.generators={ch:MockGenerator(ch) for ch in channels}
                self.router=MockRouter();self.scope=MockScope();self.mode=mode
            elif mode=="hardware":
                path=ROOT/"hardware.json"
                if not path.exists(): raise ValueError("Create hardware.json from hardware.example.json after review")
                self.profile=json.loads(path.read_text(encoding="utf-8"))
                self.mode=mode
                try:
                    self._gate()
                    self.generators=discover(self.profile)
                    if not self.generators: raise ValueError("No configured HS5 connected")
                    self.router=SerialRouter(self.profile["arduino_port"],self.shared_fault)
                except Exception:
                    self._close_devices();raise
            else: raise ValueError("Unknown connection mode")
            self.error=None
            return self.status()

    def _close_devices(self):
        failures=[]
        for device in [*self.generators.values(),self.router,self.scope]:
            if device:
                try: device.close()
                except Exception as exc: failures.append(str(exc))
        self.generators={};self.router=None;self.scope=None;self.mode="disconnected"
        if failures:
            self.error="Device close failures: "+"; ".join(failures)
            raise RuntimeError(self.error)

    def status(self):
        with self.lock:
            return {"app_revision":"20261001-r6","mode":self.mode,"devices":[{"channel":ch,"serial":g.serial,"name":getattr(g,"name","TiePie engineering HS5"),"busy":ch in self.workers, "state":self.device_state(ch)} for ch,g in self.generators.items()],
                    "queue_summary":summarize(self.jobs,{key:time.monotonic()-value for key,value in self.run_clocks.items()}),
                    "filters":dict(self.router.filters) if self.router and not self.router.failed else {},
                    "jobs":json.loads(json.dumps([j for j in self.jobs if not j.get('archived')])),"queue_enabled":sorted(self.queue_enabled),
                    "loaded":{str(ch):job["id"] for ch,job in self.loaded.items()},
                    "routes":dict(self.router.routes) if self.router else {},"reserved":dict(self.reserved),
                    "scan":json.loads(json.dumps(self.scan_state)),"error":self.error,
                    "keep_awake":{"requested":self.power.requested,"active":self.power.active,"error":self.power.error},
                    "manual_keep_awake":self.manual_awake,
                    "events":self.store.recent(),"calibration_version":self.cal.version}

    def device_state(self,ch):
        if self.error: return 'error'
        if ch in self.loaded: return 'armed'
        if self.scan_worker and ch in self.scan_state['assignments']: return 'running'
        if ch in self.workers:
            active=next((j for j in reversed(self.jobs) if j['params']['channel']==ch and j['state'] in ACTIVE),None)
            return 'running' if active and active['state']=='running' else 'armed'
        return 'ready'

    def new_job(self,p,kind):
        return {"id":uuid.uuid4().hex,"kind":kind,"params":p.model_dump(),"state":"queued",
                "queued_at":now(),"started_at":None,"ended_at":None,"completed_repetitions":0,
                "completed_blocks":[],"simulation":self.mode=="simulation"}

    def enqueue(self,p):
        if p.duration_s is None: raise ValueError("Queued entries need repetitions or a finite stimulation time")
        with self.lock:
            job=self.new_job(p,"queue");self.jobs.append(job);self.event(job,"queued")
            return job

    def _queue_edit_idle(self):
        if self.workers or self.loaded or self.scan_worker:
            raise ValueError('Stop active operations and unload before resetting or importing a queue')

    def reset_queue(self):
        with self.lock:
            self._queue_edit_idle()
            self.queue_enabled.clear()
            updated = []
            for job in self.jobs:
                if job.get('archived'): continue
                copy = {**job, 'archived': True}
                if copy['state'] == 'queued': copy.update(state='aborted', ended_at=now())
                updated.append(copy)
            self.store.save_queue_batch(updated, 'queue_reset')
            replacements = {j['id']: j for j in updated}
            self.jobs = [replacements.get(j['id'], j) for j in self.jobs]
            self.store.repair_exports()
            return {'cleared': len(updated)}

    def import_queue(self, entries):
        with self.lock:
            self._queue_edit_idle()
            self.queue_enabled.clear()
            jobs = [self.new_job(p, 'queue') for p in entries]
            self.store.save_queue_batch(jobs, 'queue_imported')
            self.jobs.extend(jobs)
            self.store.repair_exports()
            return {'imported': len(jobs), 'note': 'Added as pending entries; queues are paused'}

    def _claim(self,p,ident):
        if self.error: raise ValueError("Reconnect after resolving the reported fault before loading or running")
        if self.scan_worker: raise ValueError("Plate scan reserves both stimulation channels")
        if p.channel not in self.generators: raise ValueError("Selected configured stimulator is unavailable")
        if p.channel in self.workers or p.channel in self.loaded: raise ValueError("Channel busy or already loaded")
        if any(w in self.reserved for w in p.wells): raise ValueError("Selected well is reserved")
        self._gate(p)
        for well in p.wells: self.reserved[well]=ident

    def _release(self,ident):
        for w in list(self.reserved):
            if self.reserved[w]==ident: del self.reserved[w]

    def load(self,p):
        with self.lock:
            if p.channel in self.queue_enabled: raise ValueError("Pause this queue before manual Load")
            job=self.new_job(p,"manual")
            self._claim(p,job["id"])
            self.jobs.append(job)
            try:
                self.router.disconnect(p.channel)
                accepted=self.generators[p.channel].load(p)
                job["accepted"]=accepted
                self.loaded[p.channel]=job;self.event(job,"loaded",accepted=accepted)
            except Exception as exc:
                self.loaded.pop(p.channel,None)
                self._release(job["id"])
                self._terminal_event(job,"failed",str(exc))
                try: self.generators[p.channel].stop()
                except Exception as stop_exc: self.shared_fault(str(stop_exc))
                if isinstance(exc,RoutingFault): self.shared_fault(str(exc))
                raise
            return job

    def start_loaded(self,channel,ident):
        with self.lock:
            job=self.loaded.get(channel)
            if not job or job["id"]!=ident: raise ValueError("Load the current configuration before Start")
            del self.loaded[channel]
            self._spawn(job)

    def _spawn(self,job):
        ch=job["params"]["channel"]
        job["simulation"]=self.mode=="simulation"
        # Caller owns self.lock. Publish active state before releasing it so a
        # cancel/remove request cannot archive a job whose worker already exists.
        job["state"]="loading"
        cancel=threading.Event()
        thread=threading.Thread(target=self._run,args=(job,cancel),daemon=True)
        self.workers[ch]=(thread,cancel)
        thread.start()

    def run_queue(self,channels):
        with self.lock:
            if self.scan_worker: raise ValueError("Scan is active")
            if self.error: raise ValueError("Reconnect/recover hardware before resuming queues")
            for ch in channels:
                if ch not in self.generators: raise ValueError(f"HS5 {ch} is unavailable")
            self.queue_enabled.update(channels)

    def _dispatch(self):
        while not self.shutdown.wait(.03):
            with self.lock:
                if self.scan_worker: continue
                for ch in sorted(self.queue_enabled):
                    if ch in self.workers or ch in self.loaded: continue
                    job=next((j for j in self.jobs if j["kind"]=="queue" and j["state"]=="queued" and j["params"]["channel"]==ch),None)
                    if not job: continue
                    p=Stimulus(**job["params"])
                    if any(w in self.reserved for w in p.wells): continue
                    try:
                        self._claim(p,job["id"]);self._spawn(job)
                    except Exception as exc:
                        self.queue_enabled.discard(ch);self._release(job["id"])
                        self._terminal_event(job,"failed",str(exc))

    def _terminal_event(self,job,state,message):
        job["ended_at"]=now()
        job['error']=message
        try: self.event(job,state,error=message)
        except Exception as exc:
            # A failed log must never prevent output stopping or allow another entry.
            job["state"]="failed"
            self.shared_fault(f"Cannot persist operation status: {exc}")

    def _run(self,job,cancel):
        p=Stimulus(**job["params"]);ch=p.channel;g=self.generators[ch]
        self.power.acquire();last_end={}
        try:
            self.event(job,"loading")
            wait(cancel,0)
            g.stop();self.router.disconnect(ch)
            load_started=time.monotonic()
            accepted=g.load(p);job["accepted"]=accepted
            job["load_duration_s"]=time.monotonic()-load_started
            job['loaded_at']=now()
            self.store.save(job)
            self.store.event(job['id'],'load_completed',{'params':job['params'],'simulation':job['simulation'],'accepted':accepted,'loaded_at':job['loaded_at']})
            # Trigger primer occurs once per entry, with all-zero output and this channel disconnected.
            pre_deadline=None
            if p.trigger_in or p.trigger_out:
                self.event(job,"waiting_trigger" if p.trigger_in else "loading",detail="zero-output primer")
                edge=g.primer(p,cancel)
                pre_deadline=edge+(p.initial_off_s if p.off_s is not None else p.pre_s)
                g.load(p)
                if time.monotonic()>pre_deadline:
                    raise RuntimeError("Trigger primer and reload exceeded the requested pre-off period")
            job["started_at"]=now();self.event(job,"running",accepted=accepted)
            # Fixed origin: route/log latency consumes the available OFF time;
            # it is never added as a fresh sleep after those operations finish.
            epoch=(pre_deadline-(p.initial_off_s if p.off_s is not None else p.pre_s)
                   if pre_deadline is not None else time.monotonic())
            self.run_clocks[job['id']]=epoch
            timed_end=epoch+p.stimulation_time_s if p.stimulation_time_s is not None else None
            lead=p.initial_off_s+(0 if p.off_s is not None else p.pre_s)
            rep=0;finished=False
            while not finished and (p.repetitions==0 or rep<p.repetitions):
                for wi,well in enumerate(p.wells):
                    target=epoch+lead+rep*p.cycle_s+wi*p.on_s
                    if timed_end is not None and target+accepted['actual_on_s']>timed_end+1e-9:
                        finished=True;break
                    wait(cancel,0)
                    route_started=time.monotonic()
                    g.stop();self.router.disconnect(ch);self.router.route(ch,well,p.filter_on)
                    route_duration=time.monotonic()-route_started
                    minimum_off=p.pair_off_s if len(p.wells)==2 else p.pre_s+p.post_s
                    earliest=max(target,last_end.get(well,-float('inf'))+minimum_off)
                    wait(cancel,max(0,earliest-time.monotonic()))
                    elapsed=time.monotonic()-last_end[well] if well in last_end else None
                    lateness=time.monotonic()-target
                    tolerance=.1*p.on_s if len(p.wells)==2 else max(.1,.1*p.on_s)
                    if lateness>=tolerance:
                        raise RuntimeError(f'Start deadline missed for {well}: {lateness:.6f}s late (limit {tolerance:.6f}s). Increase OFF time or qualify a longer ON block.')
                    if elapsed is not None and len(p.wells)==2 and elapsed>=minimum_off+.1*p.on_s:
                        raise RuntimeError(f'Pair off interval {elapsed:.6f}s exceeds strict limit {minimum_off+.1*p.on_s:.6f}s')
                    if timed_end is not None and time.monotonic()+accepted['actual_on_s']>timed_end+1e-9:
                        g.stop();self.router.disconnect(ch);finished=True;break
                    with self.lock:
                        wait(cancel,0)
                        start_stamp=now();g.start();started=time.monotonic()
                    if started-target>=tolerance or (timed_end is not None and started+accepted['actual_on_s']>timed_end+1e-9):
                        raise RuntimeError('Generator start call exceeded the scheduling budget; stopping this run')
                    deadline=started+accepted['actual_on_s']
                    while time.monotonic()<deadline or not g.done():
                        if time.monotonic()>deadline+max(.1,.1*p.on_s):raise RuntimeError('Generator did not finish its finite on block')
                        wait(cancel,min(.01,max(.0001,deadline-time.monotonic())))
                    g.stop();ended=time.monotonic();last_end[well]=ended
                    self.router.disconnect(ch)
                    block={'well':well,'repetition':rep+1,'start':start_stamp,'end':now(),
                           'host_elapsed_s':ended-started,'preceding_off_s':elapsed,
                           'scheduled_start_s':target-epoch,'host_start_s':started-epoch,
                           'start_lateness_s':started-target,'routing_s':route_duration,
                           'timestamp_basis':'host_observation'}
                    job['completed_blocks'].append(block)
                    self.store.event(job['id'],'block_completed',{'params':job['params'],'simulation':job['simulation'],**block})
                    self.store.save(job)
                if not finished:
                    rep+=1;job['completed_repetitions']=rep
            # Complete the requested elapsed time with zero output if no full
            # block fits in the remaining time. Never truncate a normal block.
            end_target=timed_end if timed_end is not None else epoch+p.initial_off_s+p.cycle_s*p.repetitions
            wait(cancel,max(0,end_target-time.monotonic()))
            job["ended_at"]=now();self.event(job,"completed")
        except InterruptedError as exc:
            self._terminal_event(job,"aborted",str(exc))
        except Exception as exc:
            with self.lock: self.queue_enabled.discard(ch)
            self._terminal_event(job,"failed",str(exc))
            if isinstance(exc,RoutingFault): self.shared_fault(str(exc))
        finally:
            failures=[]
            for operation in (g.stop,lambda:self.router.disconnect(ch)):
                try: operation()
                except Exception as exc: failures.append(str(exc))
            if failures:
                message="Cleanup could not confirm stop: "+"; ".join(failures)
                try: self.event(job,"failed",error=message)
                except Exception as exc: self.error=f"{message}; log failure: {exc}"
                self.shared_fault(message)
            with self.lock:
                self._release(job["id"]);self.workers.pop(ch,None);self.run_clocks.pop(job["id"],None)
            self.power.release()

    def stop(self,channel=0):
        with self.lock:
            channels=[1,2] if channel==0 else [channel]
            for ch in channels:
                self.queue_enabled.discard(ch)
                if ch in self.workers: self.workers[ch][1].set()
                job=self.loaded.pop(ch,None)
                if job:
                    self._release(job["id"])
                    job["ended_at"]=now()
                    try: self.event(job,"aborted",reason="unloaded")
                    except Exception as exc: self.error=f"Unable to log unload: {exc}"
            if self.scan_worker: self.scan_worker[1].set()
            # Actual output stops are also performed by each worker, then routes are disconnected.
            for ch in channels:
                if ch in self.generators:
                    try: self.generators[ch].stop()
                    except Exception as exc: self.error=str(exc)

    def shared_fault(self,message):
        self.error=message
        self.stop()

    def cancel_entry(self,ident):
        with self.lock:
            job=next((j for j in self.jobs if j["id"]==ident),None)
            if not job or job["state"]!="queued": raise ValueError("Only waiting entries may be cancelled")
            self.event(job,"aborted",reason="cancelled_before_run")

    def remove_entry(self,ident):
        with self.lock:
            job=next((j for j in self.jobs if j['id']==ident),None)
            if not job or job['state'] in ACTIVE or job['state']=='loaded':
                raise ValueError('Only inactive entries can be removed')
            replacement={**job,'archived':True}
            if replacement['state']=='queued':replacement.update(state='aborted',ended_at=now())
            self.store.save_queue_batch([replacement],'entry_removed')
            self.jobs[self.jobs.index(job)]=replacement
            self.store.repair_exports()
            return {'removed':ident}

    def recover_entry(self,ident):
        with self.lock:
            job=next((j for j in self.jobs if j["id"]==ident),None)
            if not job or job["state"]!="interrupted": raise ValueError("Only interrupted entries require recovery")
            if job.get("recovered_as"): raise ValueError("This entry already has a recovery copy")
            replacement=self.enqueue(Stimulus(**job["params"]))
            job["recovered_as"]=replacement["id"]
            self.store.save(job)
            self.store.event(replacement["id"],"recovery_requested",{"source_entry":ident,"policy":"restart_full_entry"})
            return replacement

    def scan_plan(self,s):
        channels=sorted(set(s.usable_channels)&set(self.generators))
        if not channels: raise ValueError("No configured usable stimulator connected")
        return {ch:list(WELLS if len(channels)==1 else WELLS[:12] if ch==1 else WELLS[12:]) for ch in channels}

    def start_scan(self,s):
        with self.lock:
            if self.error: raise ValueError("Reconnect after resolving the reported fault before scanning")
            if self.workers or self.loaded or self.scan_worker or self.reserved:
                raise ValueError("Scan requires all stimulation to be idle and unloaded")
            if not s.wiring_confirmed: raise ValueError("Confirm scope channel assignments and external stimulator readiness first")
            self._gate(scan=True)
            assignments=self.scan_plan(s)
            try: filters=self.router.verified_filters()
            except RoutingFault as exc:
                self.shared_fault(str(exc));raise
            # Never derive scan filters from frequency or unsent UI settings.
            s=s.model_copy(update={'channel_filters':{ch:filters[ch] for ch in assignments},'filter_on':None})
            for ch in assignments:
                self.cal.arms(s.frequency_hz,s.channel_filters[ch])
                self._gate(Stimulus(channel=ch,frequency_hz=s.frequency_hz,amplitude_ma=s.amplitude_ma,filter_on=s.channel_filters[ch]))
            if self.mode=="hardware" and not self.scope: self.scope=open_scope(self.profile)
            self.queue_enabled.clear()
            ident=uuid.uuid4().hex
            self.scan_state={"id":ident,"state":"running","settings":s.model_dump(mode="json"),"assignments":assignments,
                             "started_at":now(),"results":[],"simulation":self.mode=="simulation"}
            folder=self.store.root/"scans"/ident
            folder.mkdir(parents=True,exist_ok=True)
            self._save_scan(folder,self.scan_state)
            cancel=threading.Event();thread=threading.Thread(target=self._scan,args=(s,assignments,cancel),daemon=True)
            self.scan_worker=(thread,cancel);thread.start()
            return self.scan_state

    def _scan(self,s,assignments,cancel):
        state=self.scan_state;ident=state["id"];folder=self.store.root/"scans"/ident
        folder.mkdir(parents=True,exist_ok=True)
        self.power.acquire()
        try:
            for ch in assignments:
                # Integer-cycle sine buffer, repeated only during each acquisition window.
                p=Stimulus(channel=ch,frequency_hz=s.frequency_hz,amplitude_ma=s.amplitude_ma,
                           on_s=10/s.frequency_hz,filter_on=s.channel_filters[ch])
                self.generators[ch].load(p)
            self.router.disconnect()
            for index in range(max(map(len,assignments.values()))):
                wait(cancel,0)
                pair={ch:wells[index] for ch,wells in assignments.items() if index<len(wells)}
                for ch,well in pair.items():
                    self.generators[ch].stop();self.router.disconnect(ch);self.router.route(ch,well,s.channel_filters[ch])
                for ch in pair:
                    with self.lock:
                        wait(cancel,0);self.generators[ch].start(continuous=True)
                wait(cancel,s.settling_s)
                t,records,acquisition=self.scope.capture(s,pair,self.cal,cancel)
                for ch in pair: self.generators[ch].stop()
                for ch,well in pair.items():
                    self.router.disconnect(ch)
                    record=records[ch]
                    raw_name=f"{well}_HS5_{ch}.csv"
                    with (folder/raw_name).open("w",newline="",encoding="utf-8") as raw:
                        writer=csv.writer(raw);writer.writerow(["time_s","monitor_v","stimulator_voltage_v"])
                        writer.writerows(zip(t,record["monitor"],record["voltage"]))
                    thresholds=self.profile.get("scan_quality",{}) if self.mode=="hardware" else {}
                    result=analyze(t,record["monitor"],record["voltage"],s.frequency_hz,self.cal.arms(s.frequency_hz,s.channel_filters[ch]),
                                   record["monitor_limit"],record["voltage_limit"],**thresholds)
                    result.update({"scan_id":ident,"well":well,"channel":ch,"timestamp":now(),"raw_file":raw_name,
                                   "calibration_version":self.cal.version,"frequency_hz":s.frequency_hz,
                                   "command_current_peak_ma":s.amplitude_ma,"filter_on":s.channel_filters[ch],
                                   "acquisition":acquisition,"settings":s.model_dump(mode="json"),
                                   "simulation":self.mode=="simulation"})
                    with self.lock: state["results"].append(result)
                    self.store.event(ident,"scan_well_measured",result)
                    self._save_scan(folder,state)
            state["state"]="completed"
        except InterruptedError:
            state["state"]="aborted"
        except Exception as exc:
            state["state"]="failed";state["error"]=str(exc)
            self.shared_fault(str(exc))
        finally:
            failures=[]
            for gen in self.generators.values():
                try: gen.stop()
                except Exception as exc: failures.append(str(exc))
            try: self.router.disconnect()
            except Exception as exc: failures.append(str(exc))
            if failures:
                state["state"]="failed";state["error"]="; ".join(failures);self.error=state["error"]
            state["ended_at"]=now()
            try:
                self._save_scan(folder,state)
                self.store.event(ident,"scan_"+state["state"],{"settings":state["settings"],"error":state.get("error")})
            except Exception as exc:
                state["state"]="failed";state["error"]=f"Could not save final scan status: {exc}";self.error=state["error"]
            finally:
                with self.lock: self.scan_worker=None
                self.power.release()

    @staticmethod
    def _save_scan(folder,state):
        temp=folder/"scan.tmp"
        temp.write_text(json.dumps(state,indent=2),encoding="utf-8");replace_file(temp,folder/"scan.json")
        fields=["scan_id","timestamp","well","channel","quality","impedance_ohm","phase_deg","resistance_ohm","reactance_ohm",
                "frequency_hz","command_current_peak_ma","filter_on","current_peak_a","voltage_peak_v","monitor_snr_db","voltage_snr_db",
                "calibration_version","raw_file","simulation","flags","settings","acquisition"]
        with (folder/"results.tmp").open("w",newline="",encoding="utf-8") as f:
            writer=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");writer.writeheader()
            for row in state["results"]:
                writer.writerow({k:json.dumps(v) if isinstance(v,(dict,list)) else v for k,v in row.items()})
        replace_file(folder/"results.tmp",folder/"results.csv")

    def close(self):
        self.shutdown.set();self.stop()
        threads=[w[0] for w in self.workers.values()]
        if self.scan_worker: threads.append(self.scan_worker[0])
        for thread in threads: thread.join(15)
        self.dispatcher.join(2)
        if any(t.is_alive() for t in threads):
            raise RuntimeError("Operation has not stopped; hardware cleanup remains uncertain")
        try: self._close_devices()
        finally:
            self.power.close()
            self.store.close()

    def set_keep_awake(self,enabled):
        with self.lock:
            if enabled!=self.manual_awake:
                self.power.acquire() if enabled else self.power.release()
                self.manual_awake=enabled
