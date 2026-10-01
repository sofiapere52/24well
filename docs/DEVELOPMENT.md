# Developer guide

Read [SETUP.md](SETUP.md) first. Supported deployment is an editable installation
from a complete source checkout on Windows. There is no frontend build step.

## Code map and ownership

- `src/well24/app.py`: FastAPI schemas, endpoints, local-origin mutation check,
  static files, and engine lifespan. `/docs` and `/openapi.json` describe the API.
- `models.py`: validated protocol/scan parameters and shared timing arithmetic.
- `engine.py`: hardware acceptance, reservations, queue dispatcher, manual runs,
  scan workers, cancellation, recovery and cleanup. `Engine.lock` serializes
  control actions. Device worker cancellation uses `threading.Event`.
- `devices.py`: simulated and TiePie adapters. No instrument opens on import.
- `routing.py` and `firmware/well24/well24.ino`: correlated V2 serial commands,
  channel routing, filter states, conflicts and heartbeat/watchdog.
- `waveform.py`: reusable ON buffers and preview from the same sample formula.
- `impedance.py`: calibration interpolation, prediction and scan quality checks.
- `store.py`: SQLite jobs/events, daily CSV exports and batch transactions.
- `queue_csv.py`: versioned reusable protocol import/export; `queue_summary.py`:
  nominal FIFO estimates including shared-well reservations.
- `power.py`: a dedicated thread owns the Windows keep-awake request.
- `static/app.js`, `preview.js`, `index.html`, `style.css`: UI, plotting and layout.
  `static/vendor/` contains uPlot and its license.

Root configuration and assets remain outside the Python package.
`impedance.ROOT` resolves the source root. `hardware.json` is local and ignored;
`hardware.example.json` is the tracked template. `scan_config.json` overrides
settling/cycle defaults at the scan-start API. The calibration JSON is tracked.
`resources/` preserves reference schematics, sketches and planning materials;
it is not the active firmware or application.

## Lifecycle and compatibility

Queue entries normally move from queued to loading, optionally waiting_trigger,
then running and completed/aborted/failed. Manual Load uses loaded before Start.
Restart converts persisted active/loaded jobs and running scans to interrupted.
Recovery creates a new full entry; it never resumes partway through delivery.

Reservations cover every well in an entry until cleanup, including OFF periods.
Channels can run concurrently only when reservations permit. A scan exclusively
owns stimulation and pauses both queues. Router uncertainty stops both outputs.
STOP requests cancellation and immediate generator stops; worker cleanup then
disconnects routes. Host timing is diagnostic, not physical delivery evidence.

New paired timing uses `off_s`; legacy pairs use pre/post timing when it is null.
Preserve that distinction in models, previews, scheduling, summaries and CSVs.
CSV v3 supports finite elapsed duration with repetitions zero. Imports retain
v1/v2 compatibility. Stored JSON may omit recently added model fields: validate
through `Stimulus` to apply defaults instead of assuming every key is present.

## Validation

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m pip check
node --check static/app.js
node --check static/preview.js
```

Node is needed only for the JavaScript checks, not app operation. If the usual
temporary directory is inaccessible, use a NEW path, for example
`--basetemp=data/tests-my-change`; pytest clears that path, so never point it at
runtime records or an existing data set. Tests use simulation/fakes. The optional
SDK contract test skips if `libtiepie` is absent and never opens instruments.
The preview gesture provenance test uses recorded hashes, so no sibling HS5
checkout is needed. Do not update those hashes merely to silence a failure.

Firmware compilation, if Arduino CLI and the SAM core are installed:

```powershell
arduino-cli compile --fqbn arduino:sam:arduino_due_x firmware/well24
```

Compilation is not upload or electrical qualification. Do not upload as part of
ordinary tests. UI changes also need browser simulation checks; syntax checks
alone do not prove rendered behavior. Maintain the evidence and limitations in
[VERIFICATION.md](VERIFICATION.md), without rewriting historical claims as new
verification. The installed Starlette currently emits an httpx TestClient
deprecation warning; it does not fail the tests.

Calibration regeneration is an explicit maintenance operation. The importer
`tools/import_calibration.py <PCB_Testing directory>` needs the original raw
workbooks plus `openpyxl` and NumPy; it overwrites bundled calibration JSON.
Those workbooks are not required for normal execution. Review provenance and
measurement approval separately before accepting regenerated calibration.

## Git boundaries

Commit source, tests, docs, reference resources, example configuration and bundled
calibration. Never commit `.venv`, caches, generated builds, runtime records or
local `hardware.json`. Review `git diff --cached` and `git status` before pushing.
There is no automated deployment or firmware upload tied to a Git push.
