# Short guide for AI maintainers

This is a Windows local instrument-control app, not a general web service.
Start here when context or model capacity is limited. Read only the relevant
module/test pair next; do not search generated `data/` or `.venv/` directories.

## Before editing

1. Read `README.md`, then `docs/DEVELOPMENT.md` for the code map and commands.
2. Run `git status --short`. Preserve existing user changes and runtime records.
3. Identify whether the change affects UI, protocol timing, persistence, routing,
   waveform generation or impedance. Read that module and its tests.
4. Reproduce the error with simulation or a fake. Never connect physical devices,
   upload firmware, change acceptance flags or edit calibration to pass a test.

## Invariants to preserve

- Physical acceptance is pending. Keep every hardware gate in `Engine._gate`.
- Stop output before changing a route. Routing uncertainty stops both channels.
- Reserve both wells for a whole paired entry; never route both outputs to one well.
- Mark a dispatched job active before releasing the engine lock. Pending-entry
  cancel/remove must never race with a worker that has already started.
- ON buffers are complete finite blocks. OFF periods are scheduled by the host.
  Keep deadlines tied to one monotonic origin; do not weaken timing failure guards.
- For new pairs, cycle = ON + OFF and OFF >= ON. Sequence: well 1 ON,
  well 2 ON, both off for OFF - ON. Legacy `off_s=None` retains pre/post timing.
- Repetitions zero means finite elapsed time when `stimulation_time_s` is present.
  Only the legacy manual API permits no duration; queues must be finite.
- Keep models, engine, preview, queue estimates, UI duration and CSV timing aligned.
- Startup never resumes output. Recovery creates a new full protocol entry.
- Scan folder IDs are random. Select the latest saved scan by its timestamp.
- WE calibration already includes the 10-ohm monitor. Include the 100-kilohm
  shunt once in prediction. Live scans use measured branch current directly.
- Electric field is V/m: divide well volts by 0.009 m. Do not label it V/mm.
- Source and calibration are in Git; runtime records and hardware.json are not.
- Use `python -m well24.launcher` for normal use. The last GUI connection closing
  aborts operations and exits after 3 seconds; refreshes can reconnect in that
  window. Do not replace connection tracking with background-tab JS timers.
  Bind the port before Engine startup so duplicate launches cannot edit records.

## Finish a change

Add a focused regression test for a behavior bug. Run the full Python suite and
relevant JS checks using `docs/DEVELOPMENT.md`. Update the human docs when behavior
or setup changes. If changing the browser/server revision, update BOTH
`Engine.status().app_revision` and the corresponding check in `static/app.js`.
Report what was actually tested and what remains unverified. Passing simulation
does not establish physical safety, electrical accuracy or real-time performance.

Useful test groups: `test_engine.py` (lifecycle), `test_absolute_clock.py` and
`test_switching_off.py` (timing), `test_queue_files.py` (CSV/transactions),
`test_serial_faults.py` and `test_routing_api.py` (routing/API),
`test_waveform_impedance.py` (math), `test_display_revision.py` and
`test_ui_revision.py` (display contracts), `test_review_regressions.py` (review fixes).
