# Installation and simulation guide

This guide covers the current software. Physical operation still requires every
applicable item in [ACCEPTANCE.md](ACCEPTANCE.md); it is not bench acceptance.

## Install on Windows

Install Python 3.11 or newer and Git, clone this repository, then open PowerShell
in the cloned folder. Python 3.12 was used for the recorded software checks.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[test]"
.venv\Scripts\python.exe -m pytest -q
.\run_local.bat
```

If you installed another supported Python version, substitute it in the first
command. Keep the whole source folder: an editable install uses `static/`,
`calibration/` and `scan_config.json` from that folder. Installation needs access
to dependency packages; ordinary operation uses local assets. For versions from
the original workstation, install with `-c requirements-tested.txt` as well.
That constraints file records a tested environment, not bundled packages.

Hardware preparation additionally needs `pip install -e ".[hardware]"` using the
same virtual-environment Python, the vendor USB drivers, and a reviewed local
`hardware.json`. The example profile intentionally prevents physical operation.
Do not enable acceptance flags just to make a test pass.

Both launchers open http://127.0.0.1:8002 after the server is ready. Closing the
last GUI tab/window stops operations and shuts down the server after a 3-second
grace period; refreshing/reopening within that period preserves the session.
Closing one of several GUI tabs leaves the server running. If no GUI connects
within 60 seconds of startup, the server exits. Keep a GUI tab open during runs.
Browser crashes or discarded tabs also disconnect the session and may stop runs. Only run one server against a given data directory.
Keep the server terminal open. Do not use multiple Uvicorn workers or automatic
reload when instruments are connected.

## First simulation

1. Select **Simulation** explicitly (the UI initially selects Physical hardware).
   Choose the simulated channels and click **Connect devices**.
2. Select channel 1 and one well, such as A1. Use Control, sine, 100 Hz,
   0.1 mA, 1 s ON, no triggers, one repetition, and no ramps for a first check.
3. Calculate the preview/estimate, then **Load** and **Start**. Expect completion
   and a new daily event CSV. Changing parameters requires another Load.
4. **Add to queue** saves a pending entry without Load. Run the desired channel's
   queue. Pause allows the current entry to finish; STOP aborts active work.
5. For switching, select two ordered wells and use OFF at least as long as ON.
   For example, 10 s ON / 20 s OFF alternates the two 10 s blocks, then waits
   10 s with both off. This is a 30 s repetition. Very short or zero-gap
   protocols may fail the scheduling guard even in simulation.
6. To try a simulated scan, stop/unload stimulation, expand the scan panel,
   select available channels, confirm assignments, and start. Simulation models
   signals; it does not validate physical wiring or measurement accuracy.

Queue CSV export/import saves reusable protocols, not execution checkpoints.
Reset archives existing entries; it does not erase their audit history. After
a restart, interrupted work needs explicit recovery, which starts a full new
entry. Queues never resume automatically after restart.

## Records, backup, and troubleshooting

- Default records: `data/runtime/queue.sqlite`, `events_YYYY-MM-DD.csv`, and
  `scans/<id>/` with metadata, results and raw waveforms. Git excludes `data/`.
- Back up the whole runtime directory after stopping the server. SQLite is the
  event source of truth; daily event CSVs are regenerated from it on startup.
  Raw scan files are separate and must also be retained.
- For an isolated dry run, set `$env:WELL24_DATA_DIR = "$PWD/data/my-simulation"`
  before launching. This changes records, not calibration or hardware profiles.
- A missing `.venv` requires installation above. A busy port usually means a
  server is already open. The launcher reopens an existing managed server. An
  older server must be stopped once before the new launcher can take over.
- A revision mismatch first needs Ctrl+F5 to refresh the browser interface. If
  it remains, stop/unload and restart the launcher. Updating files does not
  update a running Python process. Normal launches now bypass cached UI files.
- A physical lock requires acceptance evidence. A communication or logging
  fault requires resolving the cause and reconnecting, not bypassing a guard.
- Saved-file opening uses Windows file associations. Close a record in Excel
  if it prevents the application from replacing that CSV.

Keep the service bound to loopback on a trusted workstation. It is a local
instrument controller, without remote authentication. Keep-awake inhibits idle
sleep only; it cannot prevent shutdown, power loss or all administrative rules.
