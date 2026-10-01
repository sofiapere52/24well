# Implementation notes and remaining limitations

## Firmware changes, step by step

The original sketch is preserved under resources. The new sketch is `firmware/well24/well24.ino`; the GUI requires protocol V2.

1. Parse the entire command and validate its identifier, token count, channel, bypass value and A1–D6 well before changing pins. The original sketch could accept unsupported coordinates. Invalid commands leave the routes unchanged.
2. `id OFF 1`, `id OFF 2`, and `id OFF 0` disconnect one or both routes. The old nominal OFF input was not reachable through its normal well parser.
3. Disable both multiplexer banks for the affected channel before changing addresses or the filter pin, then enable only the selected bank. The host stops the affected generator before routing. This prevents selecting intermediate addresses while output is enabled.
4. Reject a route that is already occupied by the other stimulator. The GUI separately reserves wells for the whole entry, including both wells of a pair.
5. Return an acknowledgement only after applying the command. Include the request identifier and commanded route/bypass value. A mismatch, reset message, or missing reply makes routing uncertain and stops both stimulation channels. There is no automatic retry of a possibly applied route.
6. `id HELLO` returns `V2`; `id STATUS` returns both routes and bypass states. The host compares status with its expected state. These are software state checks, not proof of electrical continuity.
7. Start with both routes disabled. The GUI sends `PING` once per second. If five seconds pass without it, the Arduino disables both routes and reports WATCHDOG. The serial parser processes at most 32 bytes per loop, so a partial or overlong command cannot monopolize the loop and prevent the watchdog check. A new heartbeat does not restore old routes. Reconnection clears routes, pauses queues, and requires the operator to recover work. This protects against loss of the GUI/serial heartbeat; it cannot independently diagnose an analogue switch stuck closed or a failed DS5.

Protocol is 9600 baud, newline terminated: `id ROUTE channel bypass well`. Filter ON translates to bypass 0; OFF to 1. The original pin drive is preserved: bypass 0 drives the corresponding Arduino filter pin HIGH, bypass 1 LOW. Logic polarity and the assembled analogue path still require measurement.

All 48 software well/channel address assignments are compared against the original sketch. That comparison is not a continuity test of the schematic or assembled board. The new firmware compiles for Arduino Due; it has not been uploaded in this task.

## HS5 behavior and triggers

The new application retains the local-server approach and Control parameters, including the original symmetric Ramp shape. It does not alter the working HS5 application. It deliberately uses finite hardware bursts and checks amplitude/mode readback rather than silently substituting continuous generation. Only the on block is stored; off periods and repetitions are scheduled by the host.

Trigger documentation correction: the HS5 extension connector is **9-pin D-sub**, not 26-pin. EXT1, EXT2 and EXT3 correspond to pins 1, 2 and 3; pin 6 is ground. Confirm the actual breakout wiring and logic levels before connection. The user's EXT1–EXT2 breakout may not expose EXT3, so Trigger Stim cannot be assumed available through that particular cable.

Source: [TiePie HS5 manual, v2.55](https://download.tiepie.com/Documents/Manuals/Manual-HS5_v2.55.pdf). EXT1 Trigger Out, EXT2 rising-edge Trigger In and EXT3 Trigger Stim follow the mapping in the HS5 code. The new primer contains only zeros with the PCB route disconnected. It uses the legacy generator-stop trigger event selection, whose electrical edge and polarity require a scope test. The host observes the primer ending, reloads the on block, and respects the remaining pre-off interval; an overlong reload fails the entry. The 0.105 s input minimum is a software constraint, not a guaranteed hardware timing capability.

Polling a 5 ms primer may miss it on a busy system; timeout must not be interpreted as successful trigger delivery. Trigger functionality remains behind its own acceptance flag. Software timestamps never certify exact external-edge/current-delivery timing.

## EIS calibration

`calibration/stim2_pt.json` was imported from 15 raw files: three samples each for stim2 WE and CE at bypass 0 and 1 (12 arm records), plus three Pt-only device records. The importer retains source paths, SHA-256 digests, individual sample values and complex means. The individual values permit review of sample spread. PEDOT all-circuit records are excluded. Normal operation needs only this bundled JSON.

The sign convention converts the exported negative-imaginary column to complex impedance with negative imaginary parts for capacitive behavior. Magnitude and phase columns are cross-checked during import. Interpolation is linear on real and imaginary components against log frequency; no silent extrapolation.

At 100 Hz, bypass-0 arms show approximately 1.49 kΩ and −87° behavior, while bypass-1 arms are approximately 51.8 Ω (WE) and 41.8 Ω (CE), close to resistive. This supports the user's confirmed mapping of bypass 0 = filter ON. It is evidence from the records, not proof of filename provenance or assembled filter orientation.

Raw data span 1 Hz–100 kHz. The saved setup photo contains a 1 Hz instrument warning. The calibration is explicitly unapproved pending review of low-frequency sample variation and an accepted frequency range. The hardware profile must narrow the operating range accordingly. Exploratory predictions still display the warning.

WE measurements already include the 10 Ω monitoring resistor: do not add it again or silently remove it. A 10 Ω contribution is negligible only relative to an impedance much larger than 10 Ω. It would not be negligible if the remaining impedance were much lower.

For Pt prediction, form the series branch from mean WE + mean Pt + mean CE, then put that branch in parallel with 100 kΩ once. Calculate branch current by complex current division and well voltage from branch current times Pt impedance. This topology follows the supplied schematic and the user's confirmation that the other terminals were disconnected for separate arm measurements; assembled topology still needs acceptance.

For live scans, the monitor measures branch current. Use Vmonitor/10 Ω and subtract the two complex mean arm impedances from VDS5/Ibranch. Do not subtract a further 100 kΩ shunt current. TIS-like predictions use only the carrier, as requested. Nonsinusoidal prediction is a fundamental-frequency approximation and cannot bound all transient voltage peaks.

## Scope acquisition

The WD6 source identifies a WS6 DIFF. Its four analogue channels provide two simultaneous voltage/current pairs; six inputs are not required. [TiePie WS6 DIFF specifications](https://www.tiepie.com/en/wifi-oscilloscope/wifiscope-ws6-diff).

The adapter uses block acquisition, differential inputs with SafeGround disabled when exposed, automatic input ranges, editable probe scaling, normal polarity, and selected serial numbers. Actual input ranges are retained in acquisition metadata. The separate scope GUI must release the instrument. Inputs sample in one block; the two generator start calls are sequential, not hardware-synchronized. Parallel interference and settling therefore require measurement.

Quality checks reject clipping/near-range samples, nonfinite or missing samples, inadequate current, poor fitted sine SNR, unstable halves, and invalid compensated impedance. Default thresholds are development values and require bench qualification. A 0.1 mA peak branch current produces only 1 mV peak across 10 Ω. Neither this setting nor the measurement's accuracy has been physically validated.

## Software observations

Automated tests cover waveform construction, EIS arithmetic, quality rejection, original address mapping, mock route conflicts, queue/manual workflows, scans, cancellation, restart, logging at midnight, and logging failures. The browser demonstrated a completed 24-well simulated scan and the EIS/TIS-like controls.

A browser-driven 0.5 s paired simulation exceeded the allowed delay (observed 0.656 s versus a strict 0.550 s limit) and stopped further alternation. This is a successful guard check, not successful timing acceptance. Windows scheduling and synchronous durable logging can impose a practical minimum on-block duration. Do not loosen the guard to hide this; qualify the intended durations under load.

Windows accepted SetThreadExecutionState and the GUI reported keep-awake active. `powercfg /requests` inspection was unavailable without administrator elevation. Forced sleep, power policy overrides and overnight operation remain acceptance tasks. No physical outputs were intentionally operated and no bench result is claimed here.
