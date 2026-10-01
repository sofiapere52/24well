import os
import json
from datetime import datetime
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Literal
from .engine import Engine
from .models import Stimulus, Scan, StrictModel
from .impedance import ROOT
from .waveform import preview
from .queue_csv import encode, decode


class Connect(StrictModel):
    mode: Literal["simulation","hardware"]="simulation"
    channels: list[Literal[1,2]]=Field(default_factory=lambda:[1,2],min_length=1,max_length=2)


class Channels(StrictModel):
    channels: list[Literal[1,2]]=Field(default_factory=lambda:[1,2])


class Start(StrictModel):
    channel: Literal[1,2]
    entry_id: str


class Stop(StrictModel):
    channel: Literal[0,1,2]=0


class Preview(StrictModel):
    params: Stimulus
    well: str | None=None
    start: float=0
    end: float | None=None


class Awake(StrictModel):
    enabled: bool


class QueueImport(StrictModel):
    csv: str = Field(max_length=2_000_000)


class SavedFile(StrictModel):
    name: str


def create_app(data_dir=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.engine=Engine(data_dir or os.getenv("WELL24_DATA_DIR"))
        try:
            yield
        finally:
            app.state.engine.close()

    app=FastAPI(title="24 WELL GUI",lifespan=lifespan)

    @app.middleware("http")
    async def local_only(request: Request,call_next):
        # Reject cross-site mutation; server binds to loopback in both launchers.
        if request.method not in ("GET","HEAD","OPTIONS"):
            origin=request.headers.get("origin")
            if origin and origin!=str(request.base_url).rstrip("/"):
                from fastapi.responses import JSONResponse
                return JSONResponse({"detail":"Cross-origin control requests are not allowed"},status_code=403)
        return await call_next(request)

    @app.exception_handler(ValueError)
    async def invalid(request,exc):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail":str(exc)},status_code=400)

    @app.exception_handler(RuntimeError)
    async def failed(request,exc):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail":str(exc)},status_code=409)

    @app.get("/api/status")
    def status(request: Request): return request.app.state.engine.status()

    @app.post("/api/keep-awake")
    def keep_awake(body: Awake,request: Request):
        request.app.state.engine.set_keep_awake(body.enabled);return {"ok":True}

    @app.post("/api/connect")
    def connect(body: Connect,request: Request): return request.app.state.engine.connect(body.mode,body.channels)

    @app.post("/api/load")
    def load(body: Stimulus,request: Request): return request.app.state.engine.load(body)

    @app.post("/api/start")
    def start(body: Start,request: Request):
        request.app.state.engine.start_loaded(body.channel,body.entry_id);return {"ok":True}

    @app.post("/api/stop")
    def stop(body: Stop,request: Request):
        request.app.state.engine.stop(body.channel);return {"ok":True}

    @app.post("/api/queue")
    def enqueue(body: Stimulus,request: Request): return request.app.state.engine.enqueue(body)

    @app.post("/api/queue/run")
    def run(body: Channels,request: Request):
        request.app.state.engine.run_queue(body.channels);return {"ok":True}

    @app.post('/api/queue/reset')
    def reset_queue(request: Request):
        return request.app.state.engine.reset_queue()

    @app.get('/api/queue/export')
    def export_queue(request: Request):
        e = request.app.state.engine
        with e.lock: content = encode(e.jobs)
        filename = datetime.now().astimezone().strftime('queue_exp_%Y%m%d_%H%M%S_%f_')+uuid.uuid4().hex[:8]+'.csv'
        return Response(content, media_type='text/csv', headers={'Content-Disposition': f'attachment; filename="{filename}"'})

    @app.post('/api/queue/import')
    def import_queue(body: QueueImport, request: Request):
        return request.app.state.engine.import_queue(decode(body.csv))

    @app.post("/api/queue/pause")
    def pause(body: Channels,request: Request):
        e=request.app.state.engine
        with e.lock: e.queue_enabled.difference_update(body.channels)
        return {"ok":True,"note":"Current blocks finish; no new entries start"}

    @app.post("/api/queue/{ident}/cancel")
    def cancel(ident: str,request: Request):
        request.app.state.engine.cancel_entry(ident);return {"ok":True}

    @app.post("/api/queue/{ident}/recover")
    def recover(ident: str,request: Request):
        return request.app.state.engine.recover_entry(ident)

    @app.post('/api/queue/{ident}/remove')
    def remove_entry(ident: str,request: Request):
        return request.app.state.engine.remove_entry(ident)

    @app.post("/api/preview")
    def plot(body: Preview,request: Request):
        e=request.app.state.engine
        with e.lock:
            job=e.loaded.get(body.params.channel)
            rate=job["accepted"]["sample_rate_hz"] if job and job["params"]==body.params.model_dump() else None
        return preview(body.params,body.well,body.start,body.end,rate)

    @app.post("/api/estimate")
    def estimate(body: Stimulus,request: Request): return request.app.state.engine.cal.estimate(body)

    @app.post("/api/scan/plan")
    def scan_plan(body: Scan,request: Request): return request.app.state.engine.scan_plan(body)

    @app.post("/api/scan/start")
    def scan_start(body: Scan,request: Request):
        config=json.loads((ROOT/'scan_config.json').read_text(encoding='utf-8'))
        body=Scan(**{**body.model_dump(),**config})
        return request.app.state.engine.start_scan(body)

    @app.get("/api/files")
    def files(request: Request):
        root=request.app.state.engine.store.root
        return [str(p.relative_to(root)).replace("\\","/") for p in root.rglob("*") if p.suffix in (".csv",".json")]

    @app.post('/api/files/open')
    def open_saved_file(body: SavedFile, request: Request):
        root=request.app.state.engine.store.root.resolve()
        path=(root/body.name).resolve()
        if not path.is_relative_to(root) or path.suffix not in ('.csv','.json') or not path.is_file():
            raise HTTPException(404,'No such saved record')
        os.startfile(str(path))
        return {'opened':str(path)}

    app.mount("/",StaticFiles(directory=ROOT/"static",html=True),name="static")
    return app


app=create_app()
