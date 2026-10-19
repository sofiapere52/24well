# 24 WELL GUI

Separate local application for the 24-well PCB. The HS5 and WD6 projects are not modified. This implementation is ready for simulation review; it is **not accepted for unattended physical stimulation**.

## Start

New users: follow [SETUP.md](docs/SETUP.md) for installation and a simulation walkthrough.
Contributors and AI assistants: read [DEVELOPMENT.md](docs/DEVELOPMENT.md) and
[AI_GUIDE.md](AI_GUIDE.md) before editing. The [verification record](docs/VERIFICATION.md)
separates current checks from historical checks and unverified hardware behavior.

Double-click `Start_24well.vbs`, or run `run_local.bat`, the launcher opens http://127.0.0.1:8002 when ready. Closing, sleeping or discarding the GUI tab does not stop running stimulation, scans or enabled queues; use STOP ALL. The server closes itself 3 seconds after it is idle with no GUI tab open, or immediately with **Shut down server**. Run the launcher again to reopen the GUI on a running server. A queue pauses itself once it has no pending entries, so entries added later wait for **Run**. Choose Simulation and Connect devices to test without instruments. Both single-channel configurations are available in simulation.

On the original workstation, the installed `.venv` contains the application dependencies; it is excluded from Git. Normal operation uses local JavaScript, bundled uPlot 1.6.30, Python and bundled calibration JSON; it neither invokes MATLAB nor fetches plotting assets. A fresh installation requires Python 3.11+ and an editable source installation (see SETUP). Vendor USB drivers must be available before physical acceptance. Do not move this virtual environment to another computer as an installer. A standalone wheel is not a supported distribution: static assets and calibration live alongside the source tree.

## Implemented

- Control and TIS-like single-channel waveform generation, ramps, reusable on-block buffers and one preview.
- Ordered plate selection, independent channel queues, whole-entry well reservations, paired switching with a strict host-observed delay guard.
- Load/Start configuration binding, queue snapshots, STOP, restart interruption and explicit full-entry recovery.
- Daily event CSVs and SQLite state; automated one- or two-channel simulated/physical scan adapters, raw voltage records, PCB-compensated complex impedance and quality rejection.
- Versioned Arduino routing firmware, watchdog, correlated serial acknowledgements, route conflict prevention, and shared-fault stopping.
- Automatic active-operation keep-awake and a reversible manual checkbox. Closing the server releases its power request. This inhibits Windows idle sleep; it does not override an explicit shutdown, forced sleep, battery loss, or all administrative policies.

Runtime records are in `data/runtime/`. Each scan has `scan.json`, `results.csv`, and one raw CSV per measured well. Simulation records are explicitly marked. Daily event timestamps include the local UTC offset. Monotonic host time controls intervals; it is not an independent measurement of delivered current.

The interface identifies HS5 devices by their configured channel and detected serial number. Green means ready, yellow means loaded/waiting, and pulsing green means running. These are software states. The Arduino PCB LED is green while the routing board answers its 1-second heartbeat, red after a routing fault or 3 seconds without a reply (reconnect required), and grey when not connected. External current-source gain still requires configuration and verification when changing stimulators.

Queue estimates show remaining protocol time and unique wells across pending/running queue entries, including off periods. Per-well times include the entire paired protocol where applicable. Estimates assume the channels are available and exclude loading, switching and external-trigger waits. Expanded saved parameters remain open during status updates; full snapshots remain in SQLite and daily CSV events.

Plate scans always run with the PCB filter OFF (bypassed) on every scanned channel. Scope inputs and probe scales remain editable; polarity is normal and input ranges automatic. The approved hidden defaults (0.2 s settling and 100 acquisition cycles) are in `scan_config.json` and remain in saved scan metadata. They are not bench-qualified. Impedance colours are relative to valid results in the current scan: green lowest, red highest; invalid results are neutral. Both HS5 routes support all 24 wells; the two-channel scan splits rows only to share work.

The preview uses the HS5 project's wheel zoom, drag pan and reset interactions, with additional samples fetched locally when zoomed. Saved records refresh automatically.

### Reusable queue CSV

Physical hardware is the default connection selection; no device is connected automatically. Select Simulation explicitly for a dry run.

- **Reset queue** empties the displayed table, cancels pending entries and pauses both queues. Prior entries remain archived in SQLite and daily CSV records. Stop/unload active operations first.
- **Export queue CSV** downloads all visible queue entries in their original order, including previously completed entries, excluding manual runs. It saves the complete protocol, not historical execution status or device serial assignments.
- **Import queue CSV** validates the entire file before appending new pending entries. Both queues remain paused. Reset first when replacing the queue rather than appending. New entries get new IDs and timestamps; they do not resume partial runs.

Edit one row per protocol. Keep the exported headers and `format_version=3`; use channel `1` or `2`, ordered wells such as `A1;C3`, decimal points for numbers and `True`/`False` for filter/trigger fields. A blank `pulse_width_s` means the default pulse width. Use positive repetitions, or `repetitions=0` with a positive finite `stimulation_time_s`. Row order determines each channel's queue order; separate channels still run independently. Invalid rows report their CSV row number and add nothing. Imports support up to 1000 entries and 2 MB. Execution records remain separate from these reusable templates.

## Verification and acceptance

See `docs/ACCEPTANCE.md` for the remaining hardware checks and `docs/IMPLEMENTATION_NOTES.md` for firmware changes, EIS provenance, trigger correction and limits. `hardware.example.json` deliberately has no accepted limits or serial numbers. Copying it alone does not enable hardware; accepted values and evidence are required.

Run software checks with `.venv\Scripts\python.exe -m pytest -q`. Compile `firmware/well24/well24.ino` for Arduino Due using `arduino:sam:arduino_due_x`. Compilation does not upload firmware or verify physical routing.

The final operating guide will be produced after bench verification and the user's approval, as requested. Internet notifications remain deferred.


### Display and saved-file revision

Queues are shown as separate HS5 1 (green) and HS5 2 (blue) lists, with six visible compact rows and independent scroll areas. A shared export/import still contains both channels. The aggregate finish estimate includes shared-well conflicts; two disjoint equal-duration queues run concurrently. View opens full parameters and queued/loaded/started/ended timestamps. Add to queue does not require Load; loading happens immediately before execution, with a separate load-completed event.

Exports use `queue_exp_YYYYMMDD_HHMMSS_microseconds_unique.csv`. Saved-record buttons open the existing file in its Windows-associated application, rather than downloading it. Existing records remain under `data/runtime/` (daily event CSVs plus per-scan folders). EIS includes peak well voltage divided by 0.009 m, in V/m. The prediction remains open with empty values before calculation; the scan panel can be collapsed.

Preview overviews now inspect the reusable on-block sample grid in bounded chunks and preserve minimum/maximum values. They do not sparsely sample high-frequency carriers. A zoom showing at most 100 carrier cycles and 50,000 samples displays detailed sample values. Both selected wells have stacked, synchronised previews. Envelope views are labelled explicitly.

New paired entries use one ON and one per-well OFF period. OFF must be at least ON. Each repetition is first well ON → second well ON → both off for OFF − ON. Thus 10 s ON / 20 s OFF has a 30 s repetition, with 20 s off between successive blocks for either well. Equal ON/OFF alternates continuously. Ramps remain inside each complete ON block. The shared pause is included at the end of every repetition, including the last. Preview, queue estimates, execution and CSV templates use the same values.

For paired Trigger In/Out, the existing zero-output primer/reload preparation has a 0.105 s initial allowance; it is not repeated or added to each well’s OFF interval. Actual switching/scheduling overhead remains subject to the strict additional-delay guard and requires physical acceptance.

Previously saved paired entries and v1 CSVs retain their original pre/post-off timing and are labelled Legacy pair. Recreate those entries to use the new timing. New exports are CSV format_version 3 with off_s and stimulation_time_s columns; blank off_s denotes single-well or legacy timing.


### Elapsed-time stimulation and timing qualification

Set Repetitions to 0 to show Stimulation time (seconds). This is elapsed protocol time including OFF periods; loading is completed before its clock starts. The GUI requires a finite duration, and these entries can be queued/exported/imported. For compatibility, older manual API protocols with repetitions=0 and no duration still run until STOP. New CSV format 3 adds stimulation_time_s, with v1/v2 imports retained.

ON buffers load once per entry (plus the existing trigger-primer reload when used). Start deadlines are calculated from one monotonic origin. OFF is measured from the prior host-observed block end; routing/logging use the time already available in that interval. No intentional wait is added after those operations. The scheduler does not shorten a well's minimum OFF interval to catch up. It fails visibly if lateness exceeds the timing budget, rather than progressively shifting all deadlines. Host observations do not independently establish physical current timing.

When no complete ON block fits before the elapsed-time deadline, output remains zero for the rest of the requested time. A final incomplete pair may therefore contain only the first well's complete block. A start-command overrun is a fault and stops output; this is distinct from normal duration completion.

One- and two-hour accelerated tests passed for 10 s ON / 20 s OFF with injected 2 s initial loading, 20 ms routing, 5 ms per logging action and 1 ms start/stop operations. These tests use a simulated clock, not wall-clock endurance or physical hardware. Equal ON/OFF provides no scheduling slack; exact zero-gap alternation on a single switched output is not guaranteed and the failure guard may stop such a run. Longer OFF creates usable margin but does not remove the need to qualify the intended setup.

For hardware qualification, use known loads first; measure actual ON/OFF and switching gaps independently on both paths, including load/start latency, minimum and maximum delays under simultaneous queues and logging, and communication-loss response. Then run the intended 1–2 hour protocol on those loads and compare recorded delivery times with scheduled_start_s, host_start_s, start_lateness_s, routing_s and preceding_off_s in the daily event details. Confirm complete ramps and intended-well current throughout. Only then approve the operating durations/ranges for tissue work. Existing hardware acceptance gates remain in place.
