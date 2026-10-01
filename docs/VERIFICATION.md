# Verification record

This record distinguishes software verification from physical acceptance.

## Browser-owned server lifetime — 2026-10-01

The normal launchers now use `well24.launcher`, open the browser only after the
server is ready, and stop operations/shut down after the last GUI connection
closes (3-second refresh grace). An unopened GUI times out after 60 seconds.
Duplicate starts bind-check before Engine startup and reuse managed servers.
All 201 Python tests passed (11.13 s); the new lifecycle script and updated app
script passed Node syntax checks. The existing TestClient deprecation remains.

Tests exercise a real Uvicorn subprocess with two streamed browser connections:
one disconnect leaves it running; the final disconnect aborts a simulated run,
saves its aborted state and exits the process. Additional tests cover refresh,
startup timeout, stop-error handling and duplicate-launch database isolation.
This is software/network verification; no physical output or browser-vendor
sleep/discard behavior is qualified by these tests.

## Project review — 2026-10-01

197 Python tests passed (6.93 s) after review fixes. `pip check` reported no
broken requirements. Node syntax checks passed for `static/app.js` and
`static/preview.js`. One upstream Starlette/httpx TestClient deprecation warning
remains; no application test failed.

The same 197 tests also passed from a separate snapshot containing only staged
source files (7.53 s), using the existing Python environment but no sibling HS5
checkout or original runtime data. Whitespace checks passed for maintained
source/docs; original reference files in `resources/` retain their whitespace.

Fixed latest-scan restoration (timestamp order instead of random UUID order),
the dispatch/cancel/remove race, rejected hardware connections retaining an
incorrect connected mode, exceptional application lifespan cleanup, and database
handle release on normal shutdown. New regression tests cover these paths.
The preview gesture provenance check now uses hashes of the reviewed original
sections instead of requiring a sibling HS5 checkout.

Added installation/simulation instructions, a developer map and a short AI
maintenance guide. Corrected the queue CSV instructions to allow repetitions
zero with a finite stimulation time, and documented editable-install and data
backup requirements. The initial Git import excludes runtime data, virtual
environments, caches and local hardware configuration.

This review did not operate physical hardware, upload or recompile firmware,
repeat historical browser checks, or run a real-time endurance session. The
results below are dated historical evidence, not additional checks from this
review. No claim of an error-free system or physical acceptance is made.

## Historical verification — 2026-09-30

## Completed

- 165 automated Python checks passed on this Windows environment (final GUI revision run: 4.24 s). Coverage includes original 48 route/address mappings; all 2,304 dual-well/filter combinations in a mock router; malformed well rejection; serial response identifiers, timeout/reset/watchdog messages; waveform amplitudes, ramps and preview samples; complex EIS arithmetic; synthetic quality rejection; single- and dual-channel scans; queue cancellation/reservations; restart recovery; midnight exports; and logging-failure stopping.
- The installed TiePie SDK imports successfully. Its class properties were checked without opening instruments, including the scope trigger timeout and differential/SafeGround controls.
- JavaScript syntax check passed. Browser controls were exercised using keyboard activation after automated pointer clicks failed to reach the page reliably.
- Browser simulation exercised Load/Start, ordered pair selection, timing-limit failure, automatic TIS-like queue loading, EIS estimation and a complete 24-well scan with saved raw/result files.
- The Arduino Due sketch compiled successfully for `arduino:sam:arduino_due_x` (32,140 bytes in the initial build). It was not uploaded. Native compilation is not a running-firmware parser/watchdog test.
- Windows accepted the keep-awake API request, and the GUI displayed it active. The request is reversible and is released when the server closes.
- Runtime plotting and calibration are local. No MATLAB integration or remote asset URLs are used. No EIS analysis workflow was recreated.

## GUI revision verification

- Queue file follow-up: 174 software tests passed. Added complete parameter round-trips (ordered pairs, Control/TIS-like, manual filter override, pulse width, ramps and all triggers), malformed-file atomic rejection, reset persistence across restart, loaded-operation rejection and a database transaction rollback test. Browser verification exported a queue, reset the table, and imported the downloaded file as a pending entry with both queues paused. Alignment was checked from rendered control bounds; Physical hardware is selected by default without initiating a connection.

- Added checks for queue time estimates and well conflicts, per-channel filter preservation, unknown filter rejection, automatic input ranges, saved hidden scan defaults and longer protocol preview windows. The HS5 wheel/pan handler source is compared directly with the sibling project's implementation.
- Browser simulation confirmed detected simulation serials, loaded status, the running LED's `pulse-green` animation, successful manual completion and STOP, a queued one-second protocol and its estimate, expanded parameters surviving polling and job changes, EIS results, and a completed 24-well scan. Impedance results display relative green-to-red shading.
- Browser wheel zoom changed the preview from a 0–10 s extent to a narrower interval; drag and reset were exercised. No browser JavaScript errors were reported. Plot assets are bundled uPlot 1.6.30.
- A previously wall-clock-dependent paired scheduling unit test was made deterministic to test its logical sequence. The separate injected-delay failure test remains; this does not relax the production delay limit or demonstrate physical timing.
- Software and original schematic/firmware routing support 24 wells on each channel. The A–B/C–D scan split is a workload assignment, not a routing limitation. Assembled PCB continuity remains a physical acceptance item.

## Not completed / not claimed

- Physical routing, filter polarity, startup transients, current/voltage limits, grounding, hardware watchdog behavior, actual triggers and current-delivery timing.
- Known-load measurement accuracy, settling, 0.1 mA qualification, compensation, repeatability and parallel-scan interference.
- An administrator inspection of Windows power overrides: `powercfg /requests` required an elevated administrator context unavailable in this session. Extended no-sleep testing remains pending.
- Extended offline operation with the network physically disconnected, overnight endurance, or unattended-use acceptance.
- The final operating guide, which the user requested after approval of the verified system.

The 0.5 s paired browser simulation failed its delay guard at an observed 0.656 s off interval versus a 0.550 s limit. That demonstrates rejection of excessive delay; it does not qualify short paired operation. All physical-operation acceptance flags remain false in the example profile.


## Latest display revision

179 software checks passed (2026-09-30). New checks cover unique export names, opening only existing saved CSV/JSON files inside the record directory, V/mm calculation using 9 mm, anti-aliasing carrier extrema, detailed preview/buffer agreement, TIS ramps/envelopes and automatic D5 queue loading with timestamps. Browser checks confirmed D5 in each independent queue without manual loading, status chips, collapsed scan UI, stacked paired previews, and equal top/bottom bounds for the stimulation and EIS cards. No physical stimulation was performed.

Single-OFF paired scheduling was subsequently confirmed and implemented. 186 tests pass. Deterministic execution tests cover equal and longer OFF values, both wells’ measured host intervals, the full repetition duration, and preservation of complete ON blocks. Additional checks cover preview timing, concurrent aggregate queue time, validation before queuing, v2 CSV round-trips, legacy v1 preservation and initial-only trigger preparation. These are software tests, not independent measurements of delivered current.

The loaded simulations on the user's existing servers were not stopped or replaced.


## Independent clock and elapsed-time revision

193 tests pass. Accelerated 1 h and 2 h paired protocols (10 s ON / 20 s OFF) passed with injected load/routing/logging/start/stop latencies. Buffers loaded once and start targets stayed tied to one clock origin. Every preceding OFF interval met its minimum; the time-limited cutoff excluded any block that could not finish. Separate tests verified visible failure for inadequate zero-gap timing and excessive route delays, CSV duration round-trips, V/m scaling, no automatic enqueue on connection, and archival removal of an identified entry without losing audit history. No real one-hour endurance run or physical timing qualification is claimed.

The two known D5 review-test copies in the display-review data set were archived after the user requested removal; other entries remain. Browser checks showed the queue count unchanged when selecting and connecting Simulation, the time field appearing for repetitions=0, and V/m output. Selected protocol is restored above EIS on the right, with the left card extended to align.
