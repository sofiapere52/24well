import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


class Calibration:
    def __init__(self, path=None):
        self.data = json.loads((path or ROOT/"calibration/stim2_pt.json").read_text(encoding="utf-8"))
        self.version = self.data["version"]

    def value(self, name, frequency):
        g = self.data["groups"][name]
        f = np.array(g["frequency_hz"])
        if not f[0] <= frequency <= f[-1]:
            raise ValueError(f"Calibration has measurements only from {f[0]:g} to {f[-1]:g} Hz; no extrapolation")
        x = np.log10(frequency)
        return complex(np.interp(x, np.log10(f), g["real"]), np.interp(x, np.log10(f), g["imag"]))

    def arms(self, frequency, filter_on):
        bp = int(not filter_on)
        return self.value(f"bp{bp}_we", frequency)+self.value(f"bp{bp}_ce", frequency)

    def estimate(self, p):
        zpt = self.value("pt", p.frequency_hz)
        branch = self.arms(p.frequency_hz, p.filter_on)+zpt
        total = 100000*branch/(100000+branch)
        well_i = p.amplitude_ma/1000 * 100000/(100000+branch)
        return {"circuit_ohm": abs(total), "circuit_phase_deg": float(np.angle(total, deg=True)),
                "well_ohm": abs(zpt), "well_voltage_peak_v": abs(well_i*zpt),
                "electrode_distance_m": .009, "well_field_peak_v_per_m": abs(well_i*zpt)/.009,
                "required_output_peak_v": p.amplitude_ma/1000*abs(total),
                "calibration_version": self.version, "frequency_hz": p.frequency_hz,
                "notes": ["EIS-based prediction, not a live measurement.",
                          "Calibration and topology require bench acceptance; 1 Hz has an instrument warning.",
                          "100 kΩ parallel path included once; WE already includes 10 Ω."] +
                         (["Carrier-frequency approximation; Δf is ignored only for this estimate."] if p.mode == "tis_like" else []) +
                         (["Sinusoidal estimate at selected frequency; harmonic/transient peaks not predicted."] if p.shape != "sine" else [])}


def phasor(t, values, frequency):
    matrix = np.column_stack([np.cos(2*np.pi*frequency*t), np.sin(2*np.pi*frequency*t), np.ones(len(t))])
    coef, *_ = np.linalg.lstsq(matrix, values, rcond=None)
    residual = values-matrix@coef
    z = complex(coef[0], -coef[1])
    noise = float(np.sqrt(np.mean(residual**2)))
    snr = float(20*np.log10(max(abs(z)/np.sqrt(2), 1e-15)/max(noise, 1e-15)))
    # Precision of the fitted amplitude itself: broadband noise averages down over the record.
    estimate = float(20*np.log10(max(abs(z), 1e-15)/max(noise*np.sqrt(2/len(t)), 1e-15)))
    return z, snr, float(coef[2]), estimate


def analyze(t, monitor, voltage, frequency, arm_z, monitor_limit, voltage_limit,
            min_current_a=1e-6, min_snr_db=20, max_drift=.1, monitor_ohm=10., monitor_leak=0j):
    """Physical-unit, polarity-corrected arrays. Thresholds require bench acceptance.

    min_snr_db applies to the precision of each fitted 1-tone amplitude (signal over its
    estimation noise). The broadband signal-to-noise ratios are reported alongside.
    monitor_leak is the open-circuit monitor/voltage phasor ratio, removed before dividing."""
    t, monitor, voltage = map(np.asarray, (t, monitor, voltage))
    flags = []
    if len(t)<20 or len(t)!=len(monitor) or len(t)!=len(voltage) or not all(np.all(np.isfinite(a)) for a in (t, monitor, voltage)):
        return {"quality": "invalid", "flags": ["missing_or_nonfinite_samples"], "impedance_ohm": None}
    if np.any(np.diff(t)<=0):
        return {"quality": "invalid", "flags": ["nonmonotonic_time"], "impedance_ohm": None}
    if max(abs(monitor)) >= .98*monitor_limit or max(abs(voltage)) >= .98*voltage_limit:
        flags.append("clipped_or_near_range")
    mi, snri, offset_i, esti = phasor(t, monitor, frequency)
    v, snrv, offset_v, estv = phasor(t, voltage, frequency)
    current = (mi-monitor_leak*v)/monitor_ohm
    if abs(current)<min_current_a:
        flags.append("insufficient_current")
    if min(esti, estv)<min_snr_db:
        flags.append("low_signal_quality")
    halves=[]
    for sl in (slice(0,len(t)//2), slice(len(t)//2,None)):
        a = phasor(t[sl], monitor[sl], frequency)[0]
        b = phasor(t[sl], voltage[sl], frequency)[0]
        halves.append((a, b))
    for index in (0,1):
        if abs(halves[0][index]-halves[1][index]) > max_drift*max(abs(halves[0][index]),1e-15):
            flags.append("unstable_signal")
            break
    z = v/current-arm_z if abs(current)>0 else complex(float("nan"))
    if not np.isfinite(z) or z.real < 0:
        flags.append("invalid_compensated_impedance")
    return {"quality": "invalid" if flags else "valid", "flags": flags,
            "impedance_ohm": None if flags else abs(z),
            "phase_deg": None if flags else float(np.angle(z,deg=True)),
            "resistance_ohm": None if flags else z.real,
            "reactance_ohm": None if flags else z.imag,
            # Voltage across the well itself (PCB arms excluded) = well impedance x well current.
            "well_voltage_peak_v": None if flags else abs(z*current),
            "current_peak_a": abs(current), "voltage_peak_v": abs(v),
            "current_phase_deg": float(np.angle(current,deg=True)),
            "voltage_phase_deg": float(np.angle(v,deg=True)),
            "monitor_snr_db": esti, "voltage_snr_db": estv,
            "monitor_broadband_snr_db": snri, "voltage_broadband_snr_db": snrv, "monitor_ohm": monitor_ohm,
            "open_correction_a": abs(monitor_leak*v)/monitor_ohm,
            "monitor_offset_v": offset_i, "voltage_offset_v": offset_v}
