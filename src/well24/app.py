import io
import os
import re
import json
import zipfile
from datetime import datetime
import uuid
import asyncio
import traceback
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
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


class Shutdown(StrictModel):
    stop_running: bool = False


ACTIONS = {
    '/api/connect': 'Connect devices', '/api/load': 'Load', '/api/start': 'Start', '/api/stop': 'Stop',
    '/api/queue': 'Add to queue', '/api/queue/run': 'Run queue', '/api/queue/pause': 'Pause queue',
    '/api/queue/reset': 'Reset queue', '/api/queue/import': 'Import queue CSV', '/api/preview': 'Preview waveform',
    '/api/estimate': 'Estimate impedance', '/api/scan/plan': 'Show well assignments', '/api/scan/start': 'Start plate scan', '/api/scope/connect': 'Connect scope',
    '/api/files/open': 'Open saved record', '/api/keep-awake': 'Keep computer awake', '/api/shutdown': 'Shut down server',
}


def action_name(path):
    if path in ACTIONS: return ACTIONS[path]
    if path.startswith('/api/queue/'): return 'Queue entry ' + path.rsplit('/', 1)[-1]
    return path


def validation_message(exc):
    parts = []
    for error in exc.errors():
        field = '.'.join(str(k) for k in error.get('loc', ()) if k != 'body')
        text = str(error.get('msg', '')).removeprefix('Value error, ')
        parts.append(f'{field}: {text}' if field else text)
    return '; '.join(parts)


def create_app(data_dir=None, browser_lifetime=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.engine=Engine(data_dir or os.getenv("WELL24_DATA_DIR"))
        monitor = None
        if browser_lifetime is not None:
            browser_lifetime.start()
            monitor = asyncio.create_task(browser_lifetime.watch(app.state.engine))
        try:
            yield
        finally:
            if browser_lifetime is not None:
                browser_lifetime.stopping = True
            if monitor is not None:
                monitor.cancel()
                await asyncio.gather(monitor, return_exceptions=True)
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
        response = await call_next(request)
        # The UI controls instruments: never reuse a stale page, script or
        # status response after the local server has been upgraded/restarted.
        response.headers['Cache-Control'] = 'no-store'
        return response

    async def logged(request,message,status,report=None):
        if request.method=="POST" and request.url.path.startswith("/api/"):
            engine=getattr(request.app.state,"engine",None)
            if engine is not None:
                await asyncio.to_thread(engine.log_action_failure,action_name(request.url.path),message,status,report)
        return JSONResponse({"detail":message},status_code=status)

    @app.exception_handler(ValueError)
    async def invalid(request,exc):
        return await logged(request,str(exc),400)

    @app.exception_handler(RuntimeError)
    async def failed(request,exc):
        return await logged(request,str(exc),409)

    @app.exception_handler(HTTPException)
    async def http_error(request,exc):
        return await logged(request,str(exc.detail),exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def unprocessable(request,exc):
        return await logged(request,validation_message(exc),422)

    @app.exception_handler(Exception)
    async def unexpected(request,exc):
        report="".join(traceback.format_exception(exc))
        return await logged(request,f"Unexpected server error ({type(exc).__name__}): {exc}. "
                                    "Full report: data/runtime/server_errors.log",500,report)

    @app.get("/api/status")
    def status(request: Request):
        return {**request.app.state.engine.status(), 'browser_managed': browser_lifetime is not None}

    @app.get('/api/browser-session')
    async def browser_session(request: Request):
        if browser_lifetime is None:
            return Response(status_code=204)
        origin = request.headers.get('origin')
        if (request.headers.get('sec-fetch-site') == 'cross-site'
                or origin and origin != str(request.base_url).rstrip('/')):
            raise HTTPException(403, 'Browser session must use the local GUI')

        async def stream():
            connection = browser_lifetime.attach()
            try:
                while not browser_lifetime.stopping:
                    yield 'data: connected\n\n'
                    await asyncio.sleep(1)
            finally:
                browser_lifetime.detach(connection)

        return StreamingResponse(stream(), media_type='text/event-stream',
                                 headers={'Cache-Control': 'no-store'})

    @app.post('/api/shutdown')
    def shutdown(body: Shutdown, request: Request):
        if browser_lifetime is None:
            raise HTTPException(404, 'Shut down is only available when started with Start_24well.vbs')
        if request.app.state.engine.busy() and not body.stop_running:
            raise ValueError('Stimulation, a queue or a scan is still active; confirm to stop it and shut down')
        browser_lifetime.request_shutdown()
        return {'ok': True}

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
        # No engine lock: a Load uploading to the HS5 can hold it for seconds, and the
        # preview only needs one read of the loaded job (an atomic dict lookup).
        job=e.loaded.get(body.params.channel)
        accepted=job.get("accepted") if job else None
        rate=accepted["sample_rate_hz"] if accepted and job["params"]==body.params.model_dump() else None
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

    @app.post("/api/scope/connect")
    def scope_connect(request: Request): return request.app.state.engine.connect_scope()

    def scan_folder(request, ident):
        if not re.fullmatch(r"[0-9a-f]{32}", ident): raise HTTPException(404, "No such scan")
        folder = request.app.state.engine.store.root / "scans" / ident
        if not (folder / "scan.json").is_file(): raise HTTPException(404, "No such scan")
        return folder

    @app.get("/api/scan/{ident}/results.csv")
    def scan_results(ident: str, request: Request):
        folder = scan_folder(request, ident)
        return FileResponse(folder / "results.csv", media_type="text/csv", filename=f"scan_{ident[:8]}_results.csv")

    @app.get("/api/scan/{ident}/raw.zip")
    def scan_raw(ident: str, request: Request):
        folder = scan_folder(request, ident)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(folder.glob("*")):
                if path.suffix in (".csv", ".json"): archive.write(path, path.name)
        return Response(buffer.getvalue(), media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="scan_{ident[:8]}_raw.zip"'})

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
